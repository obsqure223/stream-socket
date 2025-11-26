# client/main.py

import flet as ft
from client import TrisClient
import warnings
import time
import random
import threading
import math 

# Ignora warning deprecazione
warnings.filterwarnings("ignore")

class TrisFletUI:
    def __init__(self, page: ft.Page):
        self.page = page
        self.client = TrisClient() 
        
        # Dati Utente
        self.nickname = None
        self.room_id = None
        self.my_symbol = None
        self.opponent = None
        
        # Stato Grafico
        self.current_view = "login" 
        
        # --- ELEMENTI UI STRUTTURALI ---
        self.main_content_area = ft.Container(expand=True) 
        self.sidebar_area = ft.Container(width=300, visible=False, animate_opacity=300) 
        
        # --- CHAT E LISTE DATI ---
        self.online_players = []
        self.chat_messages = ft.ListView(expand=True, spacing=5, auto_scroll=True)
        self.players_list_view = ft.ListView(expand=True, spacing=5)
        
        # Input Chat
        self.chat_input = ft.TextField(
            hint_text="Scrivi messaggio...", 
            text_size=12, 
            height=40, 
            content_padding=10,
            on_submit=self.send_chat_message,
            bgcolor="#2c2f38", 
            border_color="transparent",
            expand=True 
        )

        # --- CONTENITORE CHAT RIUTILIZZABILE ---
        self.chat_container = ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Text("CHAT ROOM", weight="bold", size=14),
                    padding=10, bgcolor="#1f2128"
                ),
                ft.Container(content=self.chat_messages, expand=True, bgcolor="#121212", padding=10),
                ft.Container(
                    content=ft.Row([
                        self.chat_input, 
                        ft.IconButton("send", icon_size=20, on_click=self.send_chat_message)
                    ]),
                    padding=5, bgcolor="#1f2128"
                )
            ], spacing=0, expand=True),
            expand=True
        )

        # --- Setup Pagina Base ---
        self.page.title = "Tris Multiplayer"
        self.page.theme_mode = ft.ThemeMode.DARK 
        self.page.bgcolor = "blueGrey900" 
        self.page.padding = 0 

        # Variabili Login/Animazione
        self.anim_running = False
        self.background_objs = []
        self.nickname_input = None 
        self.login_button = None
        self.error_text = None
        self.current_dialog = None
        self.board_items = []
        self.status_text = None

        # --- NAVBAR ---
        self.theme_icon = ft.IconButton(icon="wb_sunny_outlined", tooltip="Cambia Tema", on_click=self.toggle_theme)
        self.exit_button = ft.IconButton(icon="exit_to_app", tooltip="Esci", visible=False, on_click=self.request_exit_dialog)
        
        self.chat_drawer_button = ft.IconButton(
            icon="chat", 
            tooltip="Apri Chat", 
            visible=False, 
            # MODIFICA 1: Usa la funzione sicura invece della lambda diretta
            on_click=self.open_drawer_safe
        )

        self.page.appbar = ft.AppBar(
            leading=self.exit_button, 
            leading_width=40,
            title=ft.Text("Tris Multiplayer", weight=ft.FontWeight.BOLD),
            center_title=True,        
            bgcolor="blueGrey900", 
            actions=[
                self.chat_drawer_button,
                self.theme_icon, 
                ft.Container(width=10)
            ]
        )

        # --- COSTRUZIONE LAYOUT PRINCIPALE ---
        self.page.add(
            ft.Row(
                [
                    self.main_content_area, 
                    self.sidebar_area       
                ],
                expand=True,
                spacing=0
            )
        )

        # Avvia la prima vista
        self.show_login()

    # --- FIX 1: Apertura Drawer Sicura ---
    def open_drawer_safe(self, e):
        """Apre il drawer gestendo versioni diverse di Flet"""
        try:
            # Metodo moderno
            if hasattr(self.page, "open_end_drawer"):
                self.page.open_end_drawer()
            # Metodo fallback per vecchie versioni o Flet mobile
            elif self.page.end_drawer:
                self.page.end_drawer.open = True
                self.page.end_drawer.update()
                self.page.update()
        except Exception as ex:
            print(f"Errore apertura drawer: {ex}")

    # --- GESTIONE UI DINAMICA ---

    def build_lobby_sidebar(self):
        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Text("GIOCATORI ONLINE", weight="bold", size=14),
                    padding=10, bgcolor="#1f2128"
                ),
                ft.Container(content=self.players_list_view, height=200, bgcolor="#121212", padding=5),
                ft.Divider(height=1, color="grey"),
                self.chat_container 
            ], spacing=0),
            bgcolor="#262a33",
            border=ft.border.only(left=ft.border.BorderSide(1, "#444"))
        )

    def setup_game_drawer(self):
        self.page.end_drawer = ft.NavigationDrawer(
            controls=[
                ft.Container(
                    content=self.chat_container, 
                    expand=True,
                    padding=0,
                    height=600 
                )
            ],
            bgcolor="#262a33",
        )
        # Importante: aggiorna la pagina per registrare il drawer
        self.page.update()

    # --- VISTA 1: LOGIN ---
    def show_login(self):
        self.current_view = "login"
        
        self.sidebar_area.visible = False
        self.chat_drawer_button.visible = False
        self.exit_button.visible = False
        self.page.end_drawer = None
        
        self.stop_animation()
        time.sleep(0.1) 
        
        default_nick = self.nickname if self.nickname else ""
        self.nickname_input = ft.TextField(
            label="Nickname", width=200, text_align=ft.TextAlign.CENTER,
            value=default_nick, on_submit=self.on_connect, max_length=15,
            bgcolor="#CC37474F", border_color="white"
        )
        self.error_text = ft.Text(value="", color="red", size=14, weight=ft.FontWeight.BOLD, visible=False, text_align=ft.TextAlign.CENTER)
        self.login_button = ft.ElevatedButton("Entra in Lobby", on_click=self.on_connect, width=150)
        
        login_container = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Benvenuto a Tris!", size=30, weight=ft.FontWeight.BOLD),
                    ft.Divider(height=20, color="transparent"),
                    self.nickname_input, self.error_text, 
                    ft.Container(height=10), self.login_button
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER
            ),
            padding=40, border_radius=20, width=350, bgcolor="#B3000000", 
            border=ft.border.all(1, ft.Colors.WHITE24),
            shadow=ft.BoxShadow(spread_radius=1, blur_radius=15, color=ft.Colors.BLACK54)
        )

        self.start_background_animation()
        background_controls = [obj['control'] for obj in self.background_objs]
        
        login_stack = ft.Stack(
            controls=background_controls + [
                ft.Container(content=login_container, alignment=ft.alignment.center, expand=True)
            ],
            expand=True 
        )

        self.main_content_area.content = login_stack
        self.page.update()
        
        threading.Thread(target=self._animation_loop, daemon=True).start()

    # --- VISTA 2: LOBBY ---
    def show_lobby_view(self):
        self.current_view = "lobby"
        self.stop_animation()
        
        self.chat_drawer_button.visible = False 
        self.exit_button.visible = False 
        self.page.end_drawer = None 
        
        self.sidebar_area.content = self.build_lobby_sidebar()
        self.sidebar_area.visible = True
        
        lobby_content = ft.Container(
            content=ft.Column(
                [
                    ft.Icon("sports_esports", size=80, color="blue"),
                    ft.Text(f"Benvenuto, {self.nickname}!", size=30, weight="bold"),
                    ft.Text("Sei nella Lobby principale.", color="grey"),
                    ft.Divider(height=40, color="transparent"),
                    ft.ElevatedButton(
                        "AVVIA MATCHMAKING", icon="play_circle", width=250, height=60,
                        style=ft.ButtonStyle(bgcolor="blue", color="white", text_style=ft.TextStyle(size=18, weight="bold")),
                        on_click=self.start_matchmaking
                    ),
                    ft.Container(height=20),
                    ft.OutlinedButton("Esci (Logout)", icon="logout", on_click=self.request_exit_dialog)
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER
            ),
            alignment=ft.alignment.center, expand=True, bgcolor="blueGrey900"
        )
        
        self.main_content_area.content = lobby_content
        self.page.update()

    # --- VISTA 3: WAITING ---
    def show_waiting_view(self):
        self.current_view = "waiting"
        
        waiting_content = ft.Container(
            content=ft.Column(
                [
                    ft.ProgressRing(width=50, height=50),
                    ft.Divider(height=20, color="transparent"),
                    ft.Text("Ricerca avversario in corso...", size=20, weight="bold"),
                    ft.Text("Resta in attesa, verrai connesso appena possibile.", color="grey"),
                    ft.Divider(height=40, color="transparent"),
                    ft.OutlinedButton("Annulla Ricerca", icon="close", on_click=self.cancel_matchmaking, style=ft.ButtonStyle(color="red"))
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER
            ),
            alignment=ft.alignment.center, expand=True, bgcolor="blueGrey900"
        )
        self.main_content_area.content = waiting_content
        self.page.update()

    def start_matchmaking(self, e): 
        self.client.send({"action": "start_search"})
        self.show_waiting_view()

    def cancel_matchmaking(self, e): 
        self.client.send({"action": "leave_queue"})
        self.show_lobby_view()

    def return_to_lobby(self, e):
        # Avvisa il server che ho finito di guardare i risultati e torno in lobby
        self.client.send({"action": "back_to_lobby"})
        self.show_lobby_view()

    # --- VISTA 4: GIOCO ---
    def show_game_view(self):
        self.current_view = "game"
        self.stop_animation()
        
        self.sidebar_area.visible = False
        
        self.setup_game_drawer()
        self.chat_drawer_button.visible = True
        self.exit_button.visible = True
        
        self.board_items = [] 
        self.status_text = ft.Text(
            f"Tu sei: {self.my_symbol} (vs {self.opponent})", 
            size=20, weight=ft.FontWeight.BOLD,
            color="green" if self.my_symbol == "X" else "blue"
        )

        rows = []
        for r in range(3):
            row_controls = []
            for c in range(3):
                idx = r * 3 + c
                img = ft.Image(src="x.png", opacity=0, width=60, height=60, fit=ft.ImageFit.CONTAIN)
                btn = ft.ElevatedButton(
                    content=img, width=90, height=90,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=0),
                    on_click=lambda e, i=idx: self.on_cell_click(i)
                )
                self.board_items.append((btn, img))
                row_controls.append(btn)
            rows.append(ft.Row(controls=row_controls, alignment=ft.MainAxisAlignment.CENTER))

        game_content = ft.Container(
            content=ft.Column(
                [
                    self.status_text,
                    ft.Divider(height=20, color="transparent"),
                    ft.Column(controls=rows, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Divider(height=30, color="transparent"),
                    ft.OutlinedButton("Abbandona Partita", icon="flag", on_click=self.request_exit_dialog, style=ft.ButtonStyle(color="red"))
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER
            ),
            alignment=ft.alignment.center, expand=True, bgcolor="blueGrey900"
        )

        self.main_content_area.content = game_content
        self.page.update()

    # --- LOGICA DI GIOCO & AGGIORNAMENTO BOARD ---
    def update_board(self, board, turn, result=None):
        for i, val in enumerate(board):
            btn, img = self.board_items[i]
            if val == "X": img.src = "x.png"; img.opacity = 1
            elif val == "O": img.src = "o.png"; img.opacity = 1
            else: img.src = "x.png"; img.opacity = 0
            img.update()
            
            is_my_turn = (turn == self.my_symbol)
            is_empty = (val is None)
            game_running = (turn is not None)
            
            btn.disabled = not (is_my_turn and is_empty and game_running)
            btn.update()
            
        if self.status_text:
            if turn: 
                turn_msg = "Tocca a te!" if turn == self.my_symbol else f"Tocca a {self.opponent}"
                self.status_text.value = f"Tu sei: {self.my_symbol} - {turn_msg}"
                self.status_text.color = "white"
            else: 
                self.status_text.value = "Partita Terminata"
        self.page.update()

    def on_cell_click(self, idx):
        self.client.send({"action": "move", "player_id": self.nickname, "room_id": self.room_id, "pos": idx})

    # --- FINE PARTITA & GIOCA ANCORA ---
    def show_end_dialog(self, result):
        title_text = "PARTITA FINITA"
        msg_text = ""
        text_color = "white"

        if "disconnected" in result:
            title_text = "VITTORIA (Ritiro)"
            msg_text = "L'avversario si è disconnesso 🏃"
            text_color = "green"
        elif result == "draw":
            title_text = "PAREGGIO"
            msg_text = "Nessun vincitore 🤝"
            text_color = "orange"
        elif result == f"{self.my_symbol}_wins":
            title_text = "HAI VINTO! 🎉"
            msg_text = "Ottima partita!"
            text_color = "green"
        else:
            title_text = "HAI PERSO... 💀"
            msg_text = "Non arrenderti!"
            text_color = "red"

        end_content = ft.Container(
            content=ft.Column(
                [
                    ft.Text(title_text, size=40, weight="bold", color=text_color),
                    ft.Text(msg_text, size=20),
                    ft.Divider(height=40, color="transparent"),
                    
                    ft.ElevatedButton(
                        text="Gioca di nuovo", 
                        icon="refresh",
                        on_click=self.start_matchmaking, 
                        width=250, 
                        height=50,
                        style=ft.ButtonStyle(bgcolor="green", color="white")
                    ),
                    
                    ft.Container(height=10),
                    
                    ft.TextButton(
                        text="Torna alla Lobby",
                        icon="home",
                        on_click=self.return_to_lobby,
                        style=ft.ButtonStyle(color="grey")
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            ),
            alignment=ft.alignment.center, 
            expand=True
        )
        self.main_content_area.content = end_content
        self.page.update()

    # --- CONNESSIONE E GESTIONE ERRORI ---
    def on_connect(self, e):
        self.error_text.visible = False; self.page.update()
        nick = self.nickname_input.value.strip()
        if not nick: return
        self.nickname = nick
        self.login_button.disabled = True; self.login_button.text = "Connessione..."; self.page.update()
        
        if self.client.sock: 
            try: self.client.sock.close() 
            except: pass
        self.client.connected = False; self.client.sock = None
        
        try:
            self.client.connect()
            self.client.register_callback(self.handle_server_message)
            self.client.send({"action": "join", "player_id": self.nickname})
        except Exception as ex:
            self._handle_login_error(f"Errore Server: {ex}")

    def _handle_login_error(self, reason):
        self.error_text.value = reason; self.error_text.visible = True
        self.login_button.disabled = False; self.login_button.text = "Entra in Lobby"
        self.page.update()

    # --- NETWORKING ---
    def handle_server_message(self, msg):
        try: self._process_message(msg)
        except Exception as e: print(f"UI Error: {e}")

    def _process_message(self, msg):
        msg_type = msg.get("type")
        if msg_type == "connection_lost": self.show_crash_dialog(); return
        if msg_type == "chat_message": self.add_chat_message(msg["data"]["sender"], msg["data"]["message"]); return
        if msg_type == "player_list_update": self.online_players = msg["data"]; self.update_players_list_ui(); return
        if msg_type == "match_found":
            self.room_id = msg["data"]["game_id"]; self.my_symbol = msg["data"]["you_are"]; self.opponent = msg["data"]["opponent"]
            self.show_game_view(); return
        if msg_type == "game_state":
            data = msg["data"]; self.update_board(data["board"], data["turn"], result=data.get("result"))
            if data.get("status") == "ended": self.show_end_dialog(data["result"])
            return
        if self.current_view == "login":
            if msg.get("ok") is False: self._handle_login_error(msg.get("reason")); self.client.sock.close()
            elif msg.get("ok") is True and msg.get("status") == "lobby": self.show_lobby_view()

    # --- UTILS CHAT/LISTA ---
    def update_players_list_ui(self):
        self.players_list_view.controls.clear()
        for p in self.online_players:
            status_color = "grey"; status_text = "Offline"
            if p['status'] == 'online': status_color = "green"; status_text = "In Lobby"
            elif p['status'] == 'waiting': status_color = "orange"; status_text = "In Coda"
            elif p['status'] == 'ingame': status_color = "red"; status_text = "In Partita"
            is_me = "(Tu)" if p['name'] == self.nickname else ""
            
            self.players_list_view.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Container(width=10, height=10, border_radius=10, bgcolor=status_color),
                        ft.Column([ft.Text(f"{p['name']} {is_me}", weight="bold", size=13), ft.Text(status_text, size=10, color="grey")], spacing=2)
                    ]),
                    padding=5, border_radius=5, bgcolor="#2c2f38" if is_me else "transparent"
                )
            )
        self.page.update()

    def add_chat_message(self, sender, text):
        color = "cyan" if sender == self.nickname else "white"
        self.chat_messages.controls.append(
            ft.Column([
                ft.Text(sender, size=10, color="grey", weight="bold"),
                ft.Text(text, size=13, color=color, selectable=True)
            ], spacing=2)
        )
        self.page.update()

    def send_chat_message(self, e):
        text = self.chat_input.value.strip()
        if not text: return
        self.chat_input.value = ""
        
        # FIX 2: Try-Except sul focus
        try:
            self.chat_input.focus()
        except Exception:
            pass # Se l'input non è visibile, ignora il focus
            
        self.page.update()
        self.client.send({"action": "chat", "message": text})

    def toggle_theme(self, e):
        if self.page.theme_mode == ft.ThemeMode.DARK:
            self.page.theme_mode = ft.ThemeMode.LIGHT; self.theme_icon.icon = "dark_mode_outlined"; self.page.bgcolor = "blueGrey50"; self.page.appbar.bgcolor = "blueGrey200"
        else:
            self.page.theme_mode = ft.ThemeMode.DARK; self.theme_icon.icon = "wb_sunny_outlined"; self.page.bgcolor = "blueGrey900"; self.page.appbar.bgcolor = "blueGrey900"
        self.page.update()

    # --- ANIMAZIONI & DIALOGHI ---
    def _animation_loop(self):
        t = 0 
        while self.anim_running:
            try:
                h = self.page.height if self.page.height else 800; w = self.page.width if self.page.width else 600; t += 0.05
                for i, obj in enumerate(self.background_objs):
                    obj['y'] += obj['speed']; wave_offset = obj['amplitude'] * math.sin(t + i); obj['control'].top = obj['y']; obj['control'].left = obj['base_x'] + wave_offset
                    if obj['y'] > h: obj['y'] = -50; obj['base_x'] = random.randint(0, int(w))
                self.page.update(); time.sleep(0.02) 
            except: break

    def start_background_animation(self):
        self.anim_running = True; self.background_objs = []
        for _ in range(30):
            symbol = random.choice(["x.png", "o.png"]); img = ft.Image(src=symbol, width=random.randint(20,40), opacity=0.3, fit=ft.ImageFit.CONTAIN, left=0, top=0)
            self.background_objs.append({'control': img, 'speed': random.uniform(1,3), 'y': float(random.randint(-800,0)), 'base_x': float(random.randint(0,1000)), 'amplitude': random.randint(20,60)})
        threading.Thread(target=self._animation_loop, daemon=True).start()

    def stop_animation(self): self.anim_running = False

    def request_exit_dialog(self, e):
        self.current_dialog = ft.AlertDialog(modal=True, title=ft.Text("Conferma Uscita"), content=ft.Text("Vuoi davvero uscire?"), actions=[ft.TextButton("No", on_click=self.close_dialog), ft.TextButton("Si, Esci", on_click=self.logout, style=ft.ButtonStyle(color="red"))])
        self.page.open(self.current_dialog)

    def show_crash_dialog(self):
        self.stop_animation()
        if self.current_dialog: 
            try: self.page.close(self.current_dialog)
            except: pass
        self.current_dialog = ft.AlertDialog(modal=True, title=ft.Row([ft.Icon("error", color="red"), ft.Text("Errore Server")]), content=ft.Text("Connessione col server persa."), actions=[ft.ElevatedButton("Torna al Login", on_click=self.logout, bgcolor="red")])
        self.page.open(self.current_dialog)

    def close_dialog(self, e):
        if self.current_dialog: self.page.close(self.current_dialog); self.current_dialog = None

    def logout(self, e):
        if self.current_dialog: self.page.close(self.current_dialog)
        if self.client.sock: 
            try: self.client.sock.close()
            except: pass
        self.client.connected = False; self.show_login()

def main(page: ft.Page):
    TrisFletUI(page)

ft.app(target=main, assets_dir="assets")
