import flet as ft
import time
import random
import threading
import math
import re
import warnings

# Importiamo le nostre dipendenze
from client import TrisClient  # Assicurati che client.py sia nella stessa cartella
from settings import APP_COLORS

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
        self.is_dark = True 
        self.colors = APP_COLORS # Caricato da settings.py
        
        # Gestione Errori/Connessione (FIX BUG)
        self.expecting_disconnect = False 

        # --- RIFERIMENTI UI ---
        self.login_box_container = None
        self.nickname_input = None
        self.lobby_container = None
        self.game_container = None
        self.waiting_container = None
        self.end_container = None
        
        # --- STRUTTURA UI ---
        self.main_content_area = ft.Container(expand=True) 
        self.sidebar_area = ft.Container(width=300, visible=False, animate_opacity=300) 
        
        # --- CHAT E LISTE ---
        self.online_players = []
        self.chat_messages = ft.ListView(expand=True, spacing=5, auto_scroll=True)
        self.players_list_view = ft.ListView(expand=True, spacing=5)
        
        # Inizializza Input Chat
        c = self.colors["dark"]
        self.chat_input = ft.TextField(
            hint_text="Scrivi messaggio...", 
            text_size=12, height=40, content_padding=10,
            on_submit=self.send_chat_message,
            bgcolor=c["input_bg"], color=c["input_fg"], 
            border_color=c["border"],
            expand=True 
        )
        
        # Componenti Chat
        self.chat_header_text = ft.Text("CHAT ROOM", weight="bold", size=14, color=c["text"])
        self.chat_header_container = ft.Container(content=self.chat_header_text, padding=10, bgcolor=c["surface"])
        
        self.chat_input_container = ft.Container(
            content=ft.Row([self.chat_input, ft.IconButton("send", icon_size=20, on_click=self.send_chat_message)]),
            padding=5, bgcolor=c["surface"]
        )

        self.chat_list_container = ft.Container(content=self.chat_messages, expand=True, bgcolor="#121212", padding=10)

        self.chat_container = ft.Container(
            content=ft.Column([
                self.chat_header_container,
                self.chat_list_container,
                self.chat_input_container
            ], spacing=0, expand=True),
            expand=True
        )

        # --- SETUP PAGINA ---
        self.page.title = "Tris Multiplayer"
        self.page.theme_mode = ft.ThemeMode.DARK 
        self.page.bgcolor = c["bg"]
        self.page.padding = 0 

        # Animazione
        self.anim_running = False
        self.background_objs = []
        self.current_dialog = None
        self.board_items = []
        self.status_text = None

        # --- NAVBAR ---
        self.theme_icon = ft.IconButton(icon="wb_sunny_outlined", tooltip="Cambia Tema", on_click=self.toggle_theme)
        self.exit_button = ft.IconButton(icon="exit_to_app", tooltip="Esci", visible=False, on_click=self.request_exit_dialog)
        self.chat_drawer_button = ft.IconButton(icon="chat", tooltip="Apri Chat", visible=False, on_click=self.open_drawer_safe)

        self.page.appbar = ft.AppBar(
            leading=self.exit_button, 
            leading_width=40,
            title=ft.Text("Tris Multiplayer", weight=ft.FontWeight.BOLD),
            center_title=True,        
            bgcolor="blueGrey900", 
            actions=[self.chat_drawer_button, self.theme_icon, ft.Container(width=10)]
        )

        self.page.add(ft.Row([self.main_content_area, self.sidebar_area], expand=True, spacing=0))
        self.show_login()

    # --- HELPERS ---
    def get_c(self):
        return self.colors["dark"] if self.is_dark else self.colors["light"]

    def toggle_theme(self, e):
        self.is_dark = not self.is_dark
        mode = "dark" if self.is_dark else "light"
        c = self.colors[mode]

        self.page.theme_mode = ft.ThemeMode.DARK if self.is_dark else ft.ThemeMode.LIGHT
        self.theme_icon.icon = "wb_sunny_outlined" if self.is_dark else "dark_mode_outlined"
        self.page.bgcolor = c["bg"]
        self.page.appbar.bgcolor = "blueGrey900" if self.is_dark else "blueGrey200"

        # Aggiornamento UI manuale per componenti specifici
        self.sidebar_area.bgcolor = c["sidebar"]
        if self.sidebar_area.content:
            self.sidebar_area.content.bgcolor = c["sidebar"]
            self.sidebar_area.content.border = ft.border.only(left=ft.border.BorderSide(1, "#444" if self.is_dark else "#ddd"))
            
        self.chat_header_container.bgcolor = c["surface"]
        self.chat_header_text.color = c["text"]
        self.chat_list_container.bgcolor = "#121212" if self.is_dark else "#f5f5f5"
        self.chat_input_container.bgcolor = c["surface"]
        self.chat_input.bgcolor = c["input_bg"]
        self.chat_input.color = c["input_fg"]
        self.chat_input.border_color = c["border"]

        for ctrl in self.chat_messages.controls:
            if isinstance(ctrl, ft.Column):
                sender = ctrl.controls[0]
                msg_body = ctrl.controls[1]
                is_me = (sender.value == self.nickname) if self.nickname else False
                msg_body.color = c["me"] if is_me else c["other"]

        # Aggiornamento Viste
        if self.current_view == "login" and self.login_box_container:
            self.login_box_container.bgcolor = c["login_bg"]
            self.login_box_container.border = ft.border.all(1, c["login_border"])
            try: self.login_box_container.content.controls[0].color = c["text"]
            except: pass
            if self.nickname_input:
                self.nickname_input.bgcolor = c["input_bg"]
                self.nickname_input.color = c["input_fg"]
                self.nickname_input.border_color = "white" if self.is_dark else "blue"
        elif self.lobby_container:
            self.lobby_container.bgcolor = c["bg"]
            try:
                col = self.lobby_container.content
                col.controls[1].color = c["text"]
                col.controls[2].color = c["text_dim"]
            except: pass
        elif self.game_container:
            self.game_container.bgcolor = c["bg"]
        elif self.waiting_container:
            self.waiting_container.bgcolor = c["bg"]
        elif self.end_container:
            self.end_container.bgcolor = c["bg"]

        self.update_players_list_ui()
        self.page.update()

    def open_drawer_safe(self, e):
        try:
            if hasattr(self.page, "open_end_drawer"): self.page.open_end_drawer()
            elif self.page.end_drawer: self.page.end_drawer.open = True; self.page.end_drawer.update(); self.page.update()
        except: pass

    # --- VIEWS BUILDERS ---
    def build_lobby_sidebar(self):
        c = self.get_c()
        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Text("GIOCATORI ONLINE", weight="bold", size=14, color=c["text"]),
                    padding=10, bgcolor=c["surface"]
                ),
                ft.Container(content=self.players_list_view, height=200, bgcolor="#121212" if self.is_dark else "#f5f5f5", padding=5),
                ft.Divider(height=1, color="grey"),
                self.chat_container 
            ], spacing=0),
            bgcolor=c["sidebar"],
            border=ft.border.only(left=ft.border.BorderSide(1, "#444" if self.is_dark else "#ddd"))
        )

    def setup_game_drawer(self):
        c = self.get_c()
        self.page.end_drawer = ft.NavigationDrawer(
            controls=[ft.Container(content=self.chat_container, expand=True, padding=0, height=600)],
            bgcolor=c["sidebar"],
        )
        self.page.update()
    
    def _reset_chat(self, context_name):
        """Pulisce la chat e resetta lo stato visivo."""
        self.chat_messages.auto_scroll = False
        self.chat_messages.controls.clear()
        
        # Aggiunge un messaggio di sistema per confermare visivamente il reset
        c = self.get_c()
        self.chat_messages.controls.append(
            ft.Row([
                ft.Text(f"--- {context_name} ---", size=11, color=c["text_dim"], italic=True)
            ], alignment=ft.MainAxisAlignment.CENTER)
        )
        
        self.chat_messages.auto_scroll = True # Forza l'aggiornamento immediato del solo componente

    def show_login(self):
        self.current_view = "login"
        self.sidebar_area.visible = False
        self.chat_drawer_button.visible = False
        self.exit_button.visible = False
        self.page.end_drawer = None
        self.stop_animation()
        time.sleep(0.1) 
        
        c = self.get_c()
        default_nick = self.nickname if self.nickname else ""
        
        self.nickname_input = ft.TextField(
            label="Nickname", width=200, text_align=ft.TextAlign.CENTER,
            value=default_nick, on_submit=self.on_connect, max_length=15,
            bgcolor=c["input_bg"], color=c["input_fg"],
            border_color="white" if self.is_dark else "blue"
        )
        
        self.error_text = ft.Text(value="", color="red", size=14, weight=ft.FontWeight.BOLD, visible=False, text_align=ft.TextAlign.CENTER)
        self.login_button = ft.ElevatedButton("Entra in Lobby", on_click=self.on_connect, width=150)
        
        self.login_box_container = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Benvenuto a Tris!", size=30, weight=ft.FontWeight.BOLD, color=c["text"]),
                    ft.Divider(height=20, color="transparent"),
                    self.nickname_input, self.error_text, 
                    ft.Container(height=10), self.login_button
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER
            ),
            padding=40, border_radius=20, width=350, 
        )

        self.start_background_animation()
        background_controls = [obj['control'] for obj in self.background_objs]
        self.main_content_area.content = ft.Stack(
            controls=background_controls + [
                ft.Container(content=self.login_box_container, alignment=ft.alignment.center, expand=True)
            ],
            expand=True 
        )
        self.page.update()
        threading.Thread(target=self._animation_loop, daemon=True).start()

    def show_lobby_view(self):
        self.current_view = "lobby"
        self.stop_animation()
        c = self.get_c()
        
        # 1. Puliamo la chat (in memoria)
        self._reset_chat("")
        
        self.chat_drawer_button.visible = False 
        self.exit_button.visible = False 
        
        # 2. Rimuoviamo il Drawer (se esiste)
        self.page.end_drawer = None
        
        # 3. Costruiamo la Sidebar (che ora conterrà la chat)
        self.sidebar_area.content = self.build_lobby_sidebar()
        self.sidebar_area.visible = True
        self.sidebar_area.bgcolor = c["sidebar"]
        
        self.lobby_container = ft.Container(
            content=ft.Column(
                [
                    ft.Icon("sports_esports", size=80, color="blue"),
                    ft.Text(f"Benvenuto, {self.nickname}!", size=30, weight="bold", color=c["text"]),
                    ft.Text("Sei nella Lobby principale.", color=c["text_dim"]),
                    ft.Divider(height=40, color="transparent"),
                    ft.ElevatedButton("AVVIA MATCHMAKING", icon="play_circle", width=250, height=60, style=ft.ButtonStyle(bgcolor="blue", color="white", text_style=ft.TextStyle(size=18, weight="bold")), on_click=self.start_matchmaking),
                    ft.Container(height=20),
                    ft.OutlinedButton("Esci (Logout)", icon="logout", on_click=self.request_exit_dialog)
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER
            ),
            alignment=ft.alignment.center, expand=True, bgcolor=c["bg"]
        )
        self.main_content_area.content = self.lobby_container
        
        # 4. Aggiorniamo TUTTA la pagina (questo renderizza la chat pulita nella nuova posizione)
        self.page.update()

    def show_waiting_view(self):
        self.current_view = "waiting"
        c = self.get_c()
        self.waiting_container = ft.Container(
            content=ft.Column(
                [
                    ft.ProgressRing(width=50, height=50),
                    ft.Divider(height=20, color="transparent"),
                    ft.Text("Ricerca avversario in corso...", size=20, weight="bold", color=c["text"]),
                    ft.Text("Resta in attesa, verrai connesso appena possibile.", color=c["text_dim"]),
                    ft.Divider(height=40, color="transparent"),
                    ft.OutlinedButton("Annulla Ricerca", icon="close", on_click=self.cancel_matchmaking, style=ft.ButtonStyle(color="red"))
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER
            ),
            alignment=ft.alignment.center, expand=True, bgcolor=c["bg"]
        )
        self.main_content_area.content = self.waiting_container
        self.page.update()

    def show_game_view(self):
        self.current_view = "game"
        self.stop_animation()
        c = self.get_c()
        
        # 1. Puliamo la chat (in memoria)
        self._reset_chat("Game Chat")
        
        # 2. Nascondiamo sidebar e impostiamo il Drawer (che ora conterrà la chat)
        self.sidebar_area.visible = False
        self.setup_game_drawer() # Qui dentro la chat viene assegnata al drawer
        
        self.chat_drawer_button.visible = True
        self.exit_button.visible = True
        
        self.board_items = [] 
        self.status_text = ft.Text(f"Tu sei: {self.my_symbol} (vs {self.opponent})", size=20, weight=ft.FontWeight.BOLD, color="green" if self.my_symbol == "X" else "blue")

        rows = []
        for r in range(3):
            row_controls = []
            for c in range(3):
                idx = r * 3 + c
                img = ft.Image(src="x.png", opacity=0, width=60, height=60, fit=ft.ImageFit.CONTAIN)
                btn = ft.ElevatedButton(content=img, width=90, height=90, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=0), on_click=lambda e, i=idx: self.on_cell_click(i))
                self.board_items.append((btn, img))
                row_controls.append(btn)
            rows.append(ft.Row(controls=row_controls, alignment=ft.MainAxisAlignment.CENTER))

        self.game_container = ft.Container(
            content=ft.Column(
                [
                    self.status_text,
                    ft.Divider(height=20, color="transparent"),
                    ft.Column(controls=rows, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Divider(height=30, color="transparent"),
                    ft.OutlinedButton("Abbandona Partita", icon="flag", on_click=self.request_exit_dialog, style=ft.ButtonStyle(color="red"))
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER
            ),
            alignment=ft.alignment.center, expand=True, bgcolor=self.get_c()["bg"]
        )
        self.main_content_area.content = self.game_container
        
        # 3. Aggiorniamo TUTTA la pagina
        self.page.update()

        self.game_container = ft.Container(
            content=ft.Column(
                [
                    self.status_text,
                    ft.Divider(height=20, color="transparent"),
                    ft.Column(controls=rows, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Divider(height=30, color="transparent"),
                    ft.OutlinedButton("Abbandona Partita", icon="flag", on_click=self.request_exit_dialog, style=ft.ButtonStyle(color="red"))
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER
            ),
            alignment=ft.alignment.center, expand=True, bgcolor=self.get_c()["bg"]
        )
        self.main_content_area.content = self.game_container
        self.page.update()

        self.game_container = ft.Container(
            content=ft.Column(
                [
                    self.status_text,
                    ft.Divider(height=20, color="transparent"),
                    ft.Column(controls=rows, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Divider(height=30, color="transparent"),
                    ft.OutlinedButton("Abbandona Partita", icon="flag", on_click=self.request_exit_dialog, style=ft.ButtonStyle(color="red"))
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER
            ),
            alignment=ft.alignment.center, expand=True, bgcolor=self.get_c()["bg"]
        )
        self.main_content_area.content = self.game_container
        self.page.update()

    def show_end_dialog(self, result):
        title_text = "PARTITA FINITA"; msg_text = ""; text_color = "white"
        if "disconnected" in result: title_text = "VITTORIA (Ritiro)"; msg_text = "L'avversario si è disconnesso 🏃"; text_color = "green"
        elif result == "draw": title_text = "PAREGGIO"; msg_text = "Nessun vincitore 🤝"; text_color = "orange"
        elif result == f"{self.my_symbol}_wins": title_text = "HAI VINTO! 🎉"; msg_text = "Ottima partita!"; text_color = "green"
        else: title_text = "HAI PERSO... 💀"; msg_text = "Non arrenderti!"; text_color = "red"

        c = self.get_c()
        self.end_container = ft.Container(
            content=ft.Column(
                [
                    ft.Text(title_text, size=40, weight="bold", color=text_color),
                    ft.Text(msg_text, size=20, color=c["text"]),
                    ft.Divider(height=40, color="transparent"),
                    ft.ElevatedButton("Gioca di nuovo", icon="refresh", on_click=self.start_matchmaking, width=250, height=50, style=ft.ButtonStyle(bgcolor="green", color="white")),
                    ft.Container(height=10),
                    ft.TextButton("Torna alla Lobby", icon="home", on_click=self.return_to_lobby, style=ft.ButtonStyle(color="grey"))
                ],
                alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER
            ),
            alignment=ft.alignment.center, expand=True, bgcolor=c["bg"]
        )
        self.main_content_area.content = self.end_container
        self.page.update()

    # --- LOGICA DI GIOCO ---
    def start_matchmaking(self, e): 
        self.client.send({"action": "start_search"}); self.show_waiting_view()
    def cancel_matchmaking(self, e): 
        self.client.send({"action": "leave_queue"}); self.show_lobby_view()
    def return_to_lobby(self, e):
        self.client.send({"action": "back_to_lobby"}); self.show_lobby_view()
    def on_cell_click(self, idx):
        self.client.send({"action": "move", "player_id": self.nickname, "room_id": self.room_id, "pos": idx})

    def update_board(self, board, turn, result=None):
        # 1. Sicurezza: Se non siamo nella vista 'game', ignoriamo l'aggiornamento
        # Questo previene il crash se arriva un messaggio mentre stiamo uscendo dalla partita
        if self.current_view != "game" or not self.board_items:
            return

        # 2. Aggiorniamo le proprietà dei controlli (SENZA chiamare .update() sui singoli oggetti)
        for i, val in enumerate(board):
            if i >= len(self.board_items): break # Protezione extra
            
            btn, img = self.board_items[i]
            
            # Imposta immagine
            if val == "X": 
                img.src = "x.png"
                img.opacity = 1
            elif val == "O": 
                img.src = "o.png"
                img.opacity = 1
            else: 
                img.src = "x.png" # Placeholder
                img.opacity = 0
            
            # Calcola stato bottone
            is_my_turn = (turn == self.my_symbol)
            is_empty = (val is None)
            game_running = (turn is not None)
            
            # Aggiorna disabilitazione
            btn.disabled = not (is_my_turn and is_empty and game_running)

            # NOTA: Abbiamo rimosso img.update() e btn.update() da qui!

        # 3. Aggiorna testo stato
        if self.status_text:
            if turn: 
                turn_msg = "Tocca a te!" if turn == self.my_symbol else f"Tocca a {self.opponent}"
                self.status_text.value = f"Tu sei: {self.my_symbol} - {turn_msg}"
                self.status_text.color = self.get_c()["text"] 
            else: 
                self.status_text.value = "Partita Terminata"

        # 4. Unico aggiornamento finale della pagina
        # Questo ridisegna tutto ciò che è attualmente visibile, evitando errori su oggetti rimossi
        self.page.update()

    # --- CONNESSIONE E MESSAGGI ---
    def on_connect(self, e):
        self.error_text.visible = False
        self.expecting_disconnect = False # RESET FLAG
        self.page.update()
        
        nick_val = self.nickname_input.value.strip()
        error_msg = None
        if not nick_val: error_msg = "Il nickname non può essere vuoto."
        elif len(nick_val) < 3: error_msg = "Nickname troppo corto (min 3)."
        elif len(nick_val) > 15: error_msg = "Nickname troppo lungo (max 15)."
        elif not re.match(r"^[a-zA-Z0-9]+$", nick_val): error_msg = "Usa solo lettere e numeri."
            
        if error_msg:
            self.error_text.value = error_msg; self.error_text.visible = True; self.page.update()
            return

        self.nickname = nick_val
        self.login_button.disabled = True; self.login_button.text = "Connessione..."
        self.nickname_input.disabled = True
        self.page.update()
        
        if self.client.sock: 
            try: self.client.sock.close() 
            except: pass
        self.client.connected = False; self.client.sock = None
        
        try:
            self.client.connect()
            self.client.register_callback(self.handle_server_message)
            self.client.send({"action": "join", "player_id": self.nickname})
        except Exception as ex: 
            self.nickname_input.disabled = False
            self._handle_login_error(f"Errore Server: {ex}")

    def _handle_login_error(self, reason):
        self.error_text.value = reason; self.error_text.visible = True
        self.login_button.disabled = False; self.login_button.text = "Entra in Lobby"
        if self.nickname_input: self.nickname_input.disabled = False
        self.page.update()

    def handle_server_message(self, msg):
        try: self._process_message(msg)
        except Exception as e: print(f"UI Error: {e}")

    def _process_message(self, msg):
        msg_type = msg.get("type")
        
        # FIX PER IL LOGIN FALLITO
        if msg_type == "connection_lost":
            if self.expecting_disconnect: 
                self.expecting_disconnect = False
                return # Ignora il crash se era previsto
            self.show_crash_dialog()
            return

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
            if msg.get("ok") is False: 
                # Login fallito (es: nick doppio)
                self.expecting_disconnect = True # Imposta flag
                self._handle_login_error(msg.get("reason"))
                if self.client.sock:
                    try: self.client.sock.close()
                    except: pass
            elif msg.get("ok") is True and msg.get("status") == "lobby": 
                self.show_lobby_view()

    # --- CHAT & ALTRE FUNZIONI UI ---
    def update_players_list_ui(self):
        c = self.get_c()
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
                        ft.Column([ft.Text(f"{p['name']} {is_me}", weight="bold", size=13, color=c["text"]), ft.Text(status_text, size=10, color="grey")], spacing=2)
                    ]),
                    padding=5, border_radius=5, bgcolor=c["input_bg"] if is_me else "transparent"
                )
            )
        self.page.update()

    def add_chat_message(self, sender, text):
        c = self.get_c()
        is_me = (sender == self.nickname)
        color = c["me"] if is_me else c["other"]
        self.chat_messages.controls.append(ft.Column([ft.Text(sender, size=10, color="grey", weight="bold"), ft.Text(text, size=13, color=color, selectable=True)], spacing=2))
        self.page.update()

    def send_chat_message(self, e):
        text = self.chat_input.value.strip()
        if not text: return
        self.chat_input.value = ""; self.page.update()
        try: self.chat_input.focus()
        except: pass
        self.client.send({"action": "chat", "message": text})

    # --- ANIMAZIONE & DIALOGS ---
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
