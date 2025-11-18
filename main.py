import socket
import threading
import time
from protocollo import recv_msg, send_msg
from gameroom import GameRoom, GameRoomError

rooms = {}              
waiting_room = None     
rooms_lock = threading.Lock()
waiting_lock = threading.Lock()

def broadcast_game_state(room, data):
    disconnected_players = []
    with room.lock:
        for pid, p_conn in room.connections.items():
            try:
                send_msg(p_conn, {
                    "type": "game_state",
                    "data": data
                })
            except Exception:
                disconnected_players.append(pid)
    return disconnected_players

def client_handler(conn, addr):
    global waiting_room
    player_id = None
    current_room = None
    
    print(f"[Server] Connessione da {addr}")
    
    try:
        msg = recv_msg(conn)
        if not msg: return
        player_id = msg.get("player_id")
        if not player_id: return

        print(f"[Server] Login: {player_id}")

        # ---------------- Matchmaking Robusto ----------------
        with waiting_lock:
            # Se non c'è nessuno in attesa, crea stanza
            if waiting_room is None:
                room = GameRoom(player_id)
                room.connections[player_id] = conn
                rooms[room.id] = room
                waiting_room = room
                current_room = room
                send_msg(conn, {"ok": True, "status": "waiting"})
                print(f"[Server] {player_id} in attesa (Nuova Stanza)...")
            
            else:
                # C'è una stanza in attesa. Proviamo a unirci.
                room = waiting_room
                
                # 1. Verifichiamo se l'Host (chi ha creato la stanza) è ancora vivo.
                #    Se l'host è caduto nel frattempo, questa stanza è "spazzatura".
                host_id = list(room.players.keys())[0]
                host_conn = room.connections.get(host_id)
                
                host_is_alive = True
                try:
                    # Proviamo a mandare un ping fittizio o verifichiamo connessione
                    # (Qui ci fidiamo del fatto che se aggiungiamo e notifichiamo, l'errore emergerà)
                    pass 
                except:
                    host_is_alive = False

                if not host_is_alive:
                    print(f"[Server] Stanza trovata ma Host morto. {player_id} diventa Host.")
                    # Scartiamo la vecchia stanza
                    waiting_room = None
                    # Creiamo nuova stanza per questo giocatore
                    room = GameRoom(player_id)
                    room.connections[player_id] = conn
                    rooms[room.id] = room
                    waiting_room = room
                    current_room = room
                    send_msg(conn, {"ok": True, "status": "waiting"})
                else:
                    # Host sembra vivo, proviamo a unire
                    try:
                        room.add_player(player_id, conn)
                        waiting_room = None # Stanza piena, togliamo dalla coda
                        current_room = room
                        
                        # --- MOMENTO CRITICO: NOTIFICA START ---
                        # Se inviare il messaggio all'Host fallisce ORA, dobbiamo salvare il secondo giocatore.
                        match_started_correctly = True
                        
                        # Notifica Host
                        try:
                            opponent = player_id
                            send_msg(host_conn, {
                                "type": "match_found",
                                "data": {"game_id": room.id, "you_are": "X", "opponent": opponent}
                            })
                        except Exception as e:
                            print(f"[Server] Errore invio start a Host: {e}")
                            match_started_correctly = False
                        
                        # Notifica Joiner (Se stesso)
                        if match_started_correctly:
                            try:
                                opponent = host_id
                                send_msg(conn, {
                                    "type": "match_found",
                                    "data": {"game_id": room.id, "you_are": "O", "opponent": opponent}
                                })
                            except Exception as e:
                                print(f"[Server] Errore invio start a Joiner: {e}")
                                match_started_correctly = False

                        # ### FIX: GESTIONE FALLIMENTO START ###
                        if not match_started_correctly:
                            print(f"[Server] Match fallito durante handshake. {player_id} torna in attesa.")
                            # La stanza è bruciata. Rimuoviamola.
                            if room.id in rooms: del rooms[room.id]
                            
                            # Creiamo una NUOVA stanza per il giocatore corrente (che è vivo)
                            # Così non deve riconnettersi.
                            new_room = GameRoom(player_id)
                            new_room.connections[player_id] = conn
                            rooms[new_room.id] = new_room
                            waiting_room = new_room
                            current_room = new_room
                            send_msg(conn, {"ok": True, "status": "waiting"})
                        else:
                            print(f"[Server] Match avviato: {host_id} vs {player_id}")

                    except GameRoomError as e:
                        send_msg(conn, {"ok": False, "reason": str(e)})
                        return

        # ---------------- Loop Gioco ----------------
        while True:
            msg = recv_msg(conn)
            if msg is None: break
            
            action = msg.get("action")
            if action == "move":
                pos = msg.get("pos")
                if current_room:
                    res = current_room.apply_move(player_id, pos)
                    broadcast_game_state(current_room, res)

    except Exception as e:
        if "10054" not in str(e):
            print(f"[Server] Errore generico {player_id}: {e}")
    finally:
        conn.close()
        print(f"[Server] {player_id} disconnesso.")
        
        # Pulizia Waiting Room
        with waiting_lock:
            if waiting_room is not None and current_room is not None:
                if waiting_room.id == current_room.id:
                    waiting_room = None
        
        # Pulizia Partita in Corso
        if player_id and current_room:
            with current_room.lock:
                if player_id in current_room.connections:
                    del current_room.connections[player_id]
                
                if current_room.status == "running":
                    current_room.status = "ended"
                    # Avvisa l'altro
                    for other_conn in current_room.connections.values():
                        try:
                            send_msg(other_conn, {
                                "type": "game_state",
                                "data": {
                                    "status": "ended",
                                    "result": f"{current_room.players[player_id]}_disconnected",
                                    "board": current_room.board,
                                    "turn": None
                                }
                            })
                        except:
                            pass

def start_server(host="0.0.0.0", port=5000):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port))
    s.listen()
    print(f"[Server] Server avviato su {host}:{port}")
    while True:
        try:
            conn, addr = s.accept()
            threading.Thread(target=client_handler, args=(conn, addr), daemon=True).start()
        except:
            pass

if __name__ == "__main__":
    start_server()
