import socket
import threading
import time
import flet as ft
from protocollo import recv_msg, send_msg
from gameroom import GameRoom, GameRoomError

# STATI GLOBALI 
rooms = {}              
waiting_room = None     

# Dizionario: player_id -> {"conn": conn, "status": "online" | "waiting" | "ingame"}
players_data = {} 

# Locks
players_lock = threading.Lock() 
rooms_lock = threading.Lock()
waiting_lock = threading.Lock()
active_conn_lock = threading.Lock()

# Tracking Socket Attivi
active_connections = []     

# Stato Server
server_running = False
server_socket = None
gui_log_callback = None

def log(message):
    print(message) 
    if gui_log_callback:
        gui_log_callback(message)

# --- FUNZIONI DI UTILITÀ ---
def broadcast_player_list():
    with players_lock:
        users_list = [{"name": pid, "status": data["status"]} for pid, data in players_data.items()]
    with players_lock:
        targets = list(players_data.values())
    for p in targets:
        try: send_msg(p["conn"], {"type": "player_list_update", "data": users_list})
        except: pass

def broadcast_game_state(room, data):
    if "board" not in data: data["board"] = room.board
    if "turn" not in data: data["turn"] = room.turn
    disconnected = []
    with room.lock:
        for pid, p_conn in room.connections.items():
            try: send_msg(p_conn, {"type": "game_state", "data": data})
            except: disconnected.append(pid)
    return disconnected

# --- GESTIONE CLIENT ---
def client_handler(conn, addr):
    global waiting_room
    player_id = None    
    current_room = None 
    
    log(f"[Connect] Connessione da {addr}")
    with active_conn_lock:
        active_connections.append(conn)

    try:
        msg = recv_msg(conn)
        if not msg: return
        if msg.get("action") == "ping": return 

        requested_id = msg.get("player_id")
        if not requested_id: return

        with players_lock:
            if requested_id in players_data:
                log(f"[Login] Rifiutato: '{requested_id}' già connesso.")
                try: send_msg(conn, {"ok": False, "reason": "Nickname già in uso!"})
                except: pass
                return 
            else:
                players_data[requested_id] = {"conn": conn, "status": "online"}
                player_id = requested_id

        log(f"[Login] Entrato in Lobby: {player_id}")
        send_msg(conn, {"ok": True, "status": "lobby"}) 
        broadcast_player_list() 

        while True:
            msg = recv_msg(conn)
            if msg is None: break 
            
            action = msg.get("action")
            if action == "ping": continue

            if action == "chat":
                text = msg.get("message", "").strip()
                if text:
                    msg_obj = {"type": "chat_message", "data": {"sender": player_id, "message": text}}
                    if current_room:
                        with current_room.lock:
                            for p_conn in current_room.connections.values():
                                try: send_msg(p_conn, msg_obj)
                                except: pass
                    else:
                        with players_lock:
                            targets = [p["conn"] for p in players_data.values() if p["status"] != "ingame"]
                        for c in targets:
                            try: send_msg(c, msg_obj)
                            except: pass
            
            elif action == "start_search":
                log(f"[Matchmaking] {player_id} cerca partita...")
                with players_lock:
                    if player_id in players_data: players_data[player_id]["status"] = "waiting"
                broadcast_player_list()

                with waiting_lock:
                    if waiting_room is None:
                        room = GameRoom(player_id)
                        room.connections[player_id] = conn
                        rooms[room.id] = room
                        waiting_room = room
                        current_room = room
                        send_msg(conn, {"type": "match_status", "status": "waiting"})
                    else:
                        room = waiting_room
                        host_id = list(room.players.keys())[0]
                        host_conn = room.connections.get(host_id)
                        try:
                            room.add_player(player_id, conn)
                            waiting_room = None 
                            current_room = room
                            with players_lock:
                                players_data[host_id]["status"] = "ingame"
                                players_data[player_id]["status"] = "ingame"
                            broadcast_player_list()
                            host_symbol = room.players[host_id]
                            joiner_symbol = room.players[player_id]
                            send_msg(host_conn, {"type": "match_found", "data": {"game_id": room.id, "you_are": host_symbol, "opponent": player_id}})
                            send_msg(conn, {"type": "match_found", "data": {"game_id": room.id, "you_are": joiner_symbol, "opponent": host_id}})
                            log(f"[Match] Avviato: {host_id} vs {player_id}")
                        except GameRoomError as e:
                            send_msg(conn, {"ok": False, "reason": str(e)})

            elif action == "send_invite":
                target_id = msg.get("target_id")
                target_conn = None
                can_invite = False
                with players_lock:
                    if target_id in players_data and players_data[target_id]["status"] == "online":
                        target_conn = players_data[target_id]["conn"]
                        can_invite = True
                if can_invite and target_conn:
                    log(f"[Invito] {player_id} -> {target_id}")
                    send_msg(target_conn, {"type": "incoming_invite", "from": player_id})
                else:
                    send_msg(conn, {"type": "invite_error", "message": f"Impossibile invitare {target_id} (Occupato o Offline)."})

            elif action == "respond_invite":
                target_id = msg.get("target_id")
                response = msg.get("response")
                inviter_conn = None
                with players_lock:
                    if target_id in players_data: inviter_conn = players_data[target_id]["conn"]
                
                if response == "decline":
                    log(f"[Invito] {player_id} rifiuta {target_id}")
                    if inviter_conn: send_msg(inviter_conn, {"type": "invite_declined", "from": player_id})
                
                elif response == "accept":
                    log(f"[Invito] {player_id} ha accettato {target_id}")
                    if inviter_conn:
                        inviter_status = "offline"
                        with players_lock:
                            if target_id in players_data: inviter_status = players_data[target_id]["status"]
                        
                        if inviter_status in ["online", "waiting"]:
                            new_room = GameRoom(target_id)
                            new_room.add_player(player_id, conn)
                            new_room.turn = "X"
                            new_room.connections[target_id] = inviter_conn
                            new_room.connections[player_id] = conn
                            
                            with rooms_lock: rooms[new_room.id] = new_room
                            with players_lock:
                                players_data[target_id]["status"] = "ingame"
                                players_data[player_id]["status"] = "ingame"
                            broadcast_player_list()
                            
                            send_msg(inviter_conn, {"type": "match_found", "data": {"game_id": new_room.id, "you_are": "X", "opponent": player_id}})
                            send_msg(conn, {"type": "match_found", "data": {"game_id": new_room.id, "you_are": "O", "opponent": target_id}})
                            
                            current_room = new_room
                            time.sleep(0.5) 
                            initial_state = {"board": new_room.board, "turn": "X", "result": None, "status": "running"}
                            broadcast_game_state(new_room, initial_state)
                            log(f"[Match Invite] Avviato: {target_id} vs {player_id}")
                        else:
                            send_msg(conn, {"type": "invite_error", "message": "Invito scaduto."})

            elif action == "move":
                pos = msg.get("pos")
                if not current_room:
                    with rooms_lock:
                        for r in rooms.values():
                            if player_id in r.players: current_room = r; break
                if current_room:
                    res = current_room.apply_move(player_id, pos)
                    broadcast_game_state(current_room, res)
                    if res.get("status") == "ended":
                        log(f"[GameOver] Stanza {current_room.id[:8]}: {res.get('result')}")

            elif action == "leave_game":
                room_id = msg.get("room_id")
                if room_id in rooms:
                    game_to_close = rooms[room_id]
                    log(f"[Abbandono] {player_id} esce da {room_id[:8]}")
                    with game_to_close.lock:
                        opponent_conn = None
                        for pid, symbol in game_to_close.players.items():
                            if pid != player_id: opponent_conn = game_to_close.connections.get(pid); break
                        if opponent_conn:
                            try: send_msg(opponent_conn, {"type": "game_state", "data": {"board": game_to_close.board, "turn": None, "result": "disconnected", "status": "ended"}})
                            except: pass
                    with players_lock:
                        if player_id in players_data: players_data[player_id]["status"] = "online"
                    with rooms_lock:
                        if room_id in rooms: del rooms[room_id]
                    current_room = None
                    broadcast_player_list()

            elif action == "leave_queue":
                with waiting_lock:
                    if waiting_room and list(waiting_room.players.keys())[0] == player_id:
                        waiting_room = None
                        log(f"[Matchmaking] {player_id} ha annullato la ricerca.")
                with players_lock:
                    if player_id in players_data: players_data[player_id]["status"] = "online"
                broadcast_player_list()

            elif action == "back_to_lobby":
                log(f"[Lobby] {player_id} è tornato in lobby.")
                with players_lock:
                    if player_id in players_data: players_data[player_id]["status"] = "online"
                current_room = None
                broadcast_player_list()

    except Exception as e:
        if server_running and "10054" not in str(e):
            log(f"[Error] {player_id}: {e}")

    finally:
        with active_conn_lock:
            if conn in active_connections: active_connections.remove(conn)
        log(f"[Disconnect] {player_id if player_id else addr}")
        with players_lock:
            if player_id in players_data: del players_data[player_id]
        
        if player_id:
            room_to_close = None
            if current_room: room_to_close = current_room
            else:
                with rooms_lock:
                    for r in rooms.values():
                        if player_id in r.players: room_to_close = r; break
            if room_to_close:
                with room_to_close.lock:
                    if player_id in room_to_close.connections: del room_to_close.connections[player_id]
                    if room_to_close.status == "running":
                        room_to_close.status = "ended"
                        for other_conn in room_to_close.connections.values():
                            try: send_msg(other_conn, {"type": "game_state", "data": {"status": "ended", "result": f"{room_to_close.players[player_id]}_disconnected", "board": room_to_close.board, "turn": None}})
                            except: pass
                with rooms_lock:
                    if room_to_close.id in rooms: del rooms[room_to_close.id]

        with waiting_lock:
            if waiting_room and player_id in waiting_room.players: waiting_room = None
        try: conn.close()
        except: pass
        broadcast_player_list()

# --- SERVER THREAD LISTENER ---
def run_server_listener(sock):
    global server_running
    try:
        log(f"--- SERVER ONLINE SU PORTA 5000 ---")
        while server_running:
            try:
                conn, addr = sock.accept()
                threading.Thread(target=client_handler, args=(conn, addr), daemon=True).start()
            except OSError: break
    except Exception as e: log(f"Errore listener: {e}")
    finally: 
        log("--- SERVER OFFLINE ---")
        server_running = False

# --- GUI ---
def main(page: ft.Page):
    page.window.icon = "icon.ico"
    global gui_log_callback, server_running, server_socket
    page.title = "Tris Server Console"; page.theme_mode = ft.ThemeMode.DARK; page.window_width = 700; page.window_height = 550; page.bgcolor = "#1f2128"
    
    logs_view = ft.ListView(expand=True, spacing=5, padding=15, auto_scroll=True)
    
    def add_log_line(text):
        color = "#e0e0e0"
        if "[Errore]" in text: color = "#ff5252"
        elif "[Match]" in text: color = "#69f0ae"
        elif "[Login]" in text: color = "#40c4ff"
        elif "[Connect]" in text: color = "#9e9e9e"
        elif "--- SERVER" in text: color = "#ffd740"
        elif "[Invito]" in text: color = "orange"
        logs_view.controls.append(ft.Text(f"{time.strftime('%H:%M:%S')} | {text}", color=color, font_family="Consolas", size=13))
        page.update()
        
    gui_log_callback = add_log_line
    status_indicator = ft.Container(width=15, height=15, border_radius=15, bgcolor="red", animate=ft.Animation(500, "bounceOut"))
    status_text = ft.Text("SERVER FERMO", weight="bold", color="red")
    
    def start_server_click(e):
        global server_running, server_socket
        if server_running: return
        try:
            temp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            temp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            temp_socket.bind(("0.0.0.0", 5000))
            temp_socket.listen()
            server_socket = temp_socket
        except OSError as err:
            log(f"[Errore] Avvio fallito: Porta 5000 occupata. {err}")
            page.snack_bar = ft.SnackBar(ft.Text("ERRORE: Porta 5000 occupata, il Server è già avviato in un altra istanza.", color="white"), bgcolor="red", open=True, duration=3000)
            page.open(page.snack_bar)
            return

        server_running = True
        btn_start.disabled = True
        btn_stop.disabled = False
        status_indicator.bgcolor = "green"
        status_text.value = "SERVER ATTIVO (Port 5000)"
        status_text.color = "green"
        page.update()
        
        threading.Thread(target=run_server_listener, args=(server_socket,), daemon=True).start()

    def stop_server_click(e):
        global server_running, server_socket
        if not server_running: return
        log("Arresto server richiesto...")
        server_running = False
        
        if server_socket: 
            try: server_socket.close()
            except: pass
            
        with active_conn_lock:
            count = len(active_connections)
            for conn in active_connections: 
                try: conn.close()
                except: pass
            active_connections.clear()
            if count > 0: log(f"Chiuse forzatamente {count} connessioni attive.")
            
        btn_start.disabled = False
        btn_stop.disabled = True
        status_indicator.bgcolor = "red"
        status_text.value = "SERVER FERMO"
        status_text.color = "red"
        page.update()

    btn_start = ft.ElevatedButton("Avvia Server", icon="play_arrow", on_click=start_server_click, bgcolor="green", color="white")
    btn_stop = ft.ElevatedButton("Ferma Server", icon="stop", on_click=stop_server_click, bgcolor="red", color="white", disabled=True)
    
    page.add(
        ft.Container(content=ft.Row([ft.Row([ft.Icon("dns", size=30, color="blue"), ft.Text("Tris Server", size=24, weight="bold")]), ft.Row([status_indicator, status_text], alignment="center")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), padding=10, bgcolor="#2c2f38", border_radius=10),
        ft.Container(content=ft.Row([btn_start, btn_stop], alignment=ft.MainAxisAlignment.CENTER, spacing=20), padding=10),
        ft.Text("Console Logs:", size=14, color="grey"),
        ft.Container(content=logs_view, expand=True, bgcolor="#121212", border=ft.border.all(1, "#333333"), border_radius=10, margin=ft.margin.only(top=10)),
        ft.Text("v1.0 by Giuseppe E. Giuffrida - Raffaele Romeo - Karol Scandurra", size=10, color="grey", text_align="center")
    )

if __name__ == "__main__":
    ft.app(target=main)
