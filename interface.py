import flet as ft
import time
import random
import threading
import math
import re
import warnings

# Importiamo le nostre dipendenze
from client import TrisClient
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
        self.colors = APP_COLORS
        self.is_mobile = False

        # Gestione Errori/Connessione
        self.expecting_disconnect = False

        # --- CREAZIONE DELLE DUE CHAT ---
        self.lobby_chat_ui = self._build_chat_components("LOBBY CHAT")
        self.game_chat_ui = self._build_chat_components("GAME CHAT")

        # Lista giocatori e ListView
        self.online_players = []
        self.players_list_view = ft.ListView(expand=True, spacing=5, padding=5)

        # --- SETUP PAGINA ---
        self.page.title = "Tris Multiplayer"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = self.get_c()["bg"]
        self.page.padding = 0
        
        # Evento ridimensionamento
        self.page.on_resized = self.on_page_resize

        # Animazione
        self.anim_running = False
        self.background_objs = []
        self.current_dialog = None
        self.board_items = []
        self.status_text = None

        # --- CONTAINER PRINCIPALI ---
        
        # 1. Area di Gioco / Login (Si espande)
        self.main_content_area = ft.Container(expand=True, padding=10)
        
        # 2. Sidebar per Desktop (Fissa a destra, width 300)
        self.sidebar_area = ft.Container(
            width=300, 
            visible=False, 
            animate_opacity=300, 
            bgcolor=self.get_c()["sidebar"],
            border=ft.border.only(left=ft.border.BorderSide(1, "#444"))
        )

        # 3. Overlay per Mobile (Sostituisce il NavigationDrawer)
        # Parte nascosto a destra (offset x=1) e scivola dentro (offset x=0)
        # CORREZIONE: Usa ft.Offset e ft.Animation diretti
        self.mobile_overlay = ft.Container(
            visible=False,
            expand=True,
            bgcolor=self.get_c()["sidebar"],
            padding=0,
            offset=ft.Offset(1, 0), 
            animate_offset=ft.Animation(300, ft.AnimationCurve.EASE_OUT),
        )

        # --- NAVBAR ---
        self.exit_button = ft.IconButton(
            icon="exit_to_app", 
            tooltip="Esci", 
            visible=False, 
            on_click=self.request_exit_dialog
        )
        
        self.chat_drawer_button = ft.IconButton(
            icon="chat", 
            tooltip="Apri Chat", 
            visible=False, 
            on_click=self.toggle_mobile_overlay
        )

        self.page.appbar = ft.AppBar(
            leading=self.exit_button,
            leading_width=40,
            title=ft.Text("Tris Multiplayer", weight=ft.FontWeight.BOLD),
            center_title=True,
            bgcolor="blueGrey900",
            actions=[self.chat_drawer_button, ft.Container(width=10)]
        )

        # --- LAYOUT PRINCIPALE (STACK) ---
        # Usiamo uno Stack per poter sovrapporre l'overlay mobile
        self.page.add(
            ft.Stack(
                controls=[
                    # Livello Base: Row con Contenuto e Sidebar Desktop
                    ft.Row(
                        controls=[self.main_content_area, self.sidebar_area],
                        expand=True,
                        spacing=0
                    ),
                    # Livello Superiore: Overlay Mobile (inizialmente fuori schermo)
                    self.mobile_overlay
                ],
                expand=True
            )
        )

        self.check_responsive_layout()
        self.show_login()

    # --- HELPERS ---
    def get_c(self):
        return self.colors["dark"]

    # --- COSTRUZIONE CHAT (Componenti sciolti) ---
    def _build_chat_components(self, title):
        """Costruisce i pezzi della chat separati per poterli assemblare nel layout."""
        c = self.get_c()
        
        # Lista messaggi (Unico elemento che deve scrollare ed espandersi)
        msg_list = ft.ListView(expand=True, spacing=5, auto_scroll=True, padding=10)
        list_container = ft.Container(content=msg_list, expand=True, bgcolor="#121212")

        # Input
        inp = ft.TextField(
            hint_text="Messaggio...", text_size=14, height=45, content_padding=10,
            on_submit=lambda e: self.send_chat_message(e, inp),
            bgcolor=c["input_bg"], color=c["input_fg"], 
            border_color=c["border"], expand=True
        )
        
        header = ft.Container(
            content=ft.Text(title, weight="bold", size=14, color=c["text"]), 
            padding=10, bgcolor=c["surface"]
        )
        
        inp_container = ft.Container(
            content=ft.Row([inp, ft.IconButton("send", icon_size=20, on_click=lambda e: self.send_chat_message(e, inp))]), 
            padding=5, bgcolor=c["surface"]
        )

        return {
            "list": msg_list, 
            "header": header, 
            "list_container": list_container, 
            "input_container": inp_container
        }

    # --- RESPONSIVITÀ ---
    def on_page_resize(self, e):
        self.check_responsive_layout()

    def check_responsive_layout(self):
        width = self.page.width
        is_now_mobile = width < 800

        if is_now_mobile != self.is_mobile:
            self.is_mobile = is_now_mobile
            self.refresh_layout_state()
            self.page.update()

    def refresh_layout_state(self):
        """Aggiorna la visibilità di Sidebar Desktop vs Pulsante Mobile"""
        if self.is_mobile:
            # Mobile: Nascondi sidebar desktop
            self.sidebar_area.visible = False
            # Mostra pulsante chat solo se loggati
            self.chat_drawer_button.visible = (self.current_view in ["lobby", "game"])
        else:
            # Desktop: Mostra sidebar solo in lobby
            self.sidebar_area.visible = (self.current_view == "lobby")
            # Mostra pulsante chat solo in game (per aprire overlay temporaneo anche su desktop se serve)
            self.chat_drawer_button.visible = (self.current_view == "game")
            
            # Se torniamo a desktop, chiudi overlay mobile e ripopola sidebar
            self.mobile_overlay.offset = ft.Offset(1, 0)
            self.mobile_overlay.visible = False
            
            if self.current_view == "lobby":
                self.sidebar_area.content = self.build_sidebar_content(for_mobile=False)

    # --- GESTIONE OVERLAY MOBILE (Il "Drawer" custom) ---
    def toggle_mobile_overlay(self, e):
        # Se è nascosto (offset x=1), lo mostriamo
        if self.mobile_overlay.offset.x == 1:
            # 1. Costruiamo il contenuto fresco
            content = self.build_sidebar_content(for_mobile=True)
            self.mobile_overlay.content = content
            self.mobile_overlay.visible = True
            self.mobile_overlay.offset = ft.Offset(0, 0)
        else:
            # Chiudiamo
            self.mobile_overlay.offset = ft.Offset(1, 0)
        
        self.page.update()

    def close_mobile_overlay(self):
        if self.mobile_overlay.visible:
            self.mobile_overlay.offset = ft.Offset(1, 0)
            self.page.update()

    # --- GENERATORE DI CONTENUTO SIDEBAR/OVERLAY ---
    def build_sidebar_content(self, for_mobile=False):
        """
        Crea la colonna layout perfetta.
        Usata sia per la Sidebar Desktop che per l'Overlay Mobile.
        """
        c = self.get_c()
        
        # Determiniamo quale chat mostrare
        chat_ui = self.lobby_chat_ui if self.current_view == "lobby" else self.game_chat_ui
        
        controls_list = []

        # 1. Tasto chiudi (Solo per Mobile Overlay)
        if for_mobile:
            controls_list.append(
                ft.Container(
                    content=ft.Row([
                        ft.Text("Menu", weight="bold", size=16),
                        ft.IconButton(ft.Icons.CLOSE, on_click=self.toggle_mobile_overlay)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=10, bgcolor=c["surface"]
                )
            )

        # 2. Sezione Giocatori (Solo in Lobby)
        if self.current_view == "lobby":
            controls_list.append(
                ft.Container(
                    content=ft.Text("GIOCATORI ONLINE", weight="bold", size=14, color=c["text"]), 
                    padding=10, bgcolor=c["surface"]
                )
            )
            # Lista Giocatori con altezza fissa (es. 200px)
            controls_list.append(
                ft.Container(
                    content=self.players_list_view, 
                    height=200, 
                    bgcolor="#121212", 
                    padding=0
                )
            )
            controls_list.append(ft.Divider(height=1, thickness=1, color="grey"))

        # 3. Sezione Chat (Header, Lista, Input)
        controls_list.append(chat_ui["header"])
        
        # LA LISTA MESSAGGI: expand=True per prendere tutto lo spazio rimasto
        controls_list.append(chat_ui["list_container"]) 
        
        controls_list.append(chat_ui["input_container"])

        # Restituiamo la Colonna Maestra
        return ft.Column(
            controls=controls_list,
            spacing=0,
            expand=True # Riempie tutta l'altezza verticale
        )

    # --- VISTE ---
    def show_login(self):
        self.current_view = "login"
        self.sidebar_area.visible = False
        self.chat_drawer_button.visible = False
        self.exit_button.visible = False
        self.close_mobile_overlay()
        self.stop_animation()
        time.sleep(0.1) 
        
        c = self.get_c()
        default_nick = self.nickname if self.nickname else ""
        
        self.nickname_input = ft.TextField(
            label="Nickname", width=200, text_align=ft.TextAlign.CENTER,
            value=default_nick, on_submit=self.on_connect, max_length=15,
            bgcolor=c["input_bg"], color=c["input_fg"], border_color="white"
        )
        
        self.error_text = ft.Text(
            value="", color="red", size=14, weight=ft.FontWeight.BOLD, 
            visible=False, text_align=ft.TextAlign.CENTER
        )
        self.login_button = ft.ElevatedButton("Entra in Lobby", on_click=self.on_connect, width=150)
        
        self.login_box_container = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Benvenuto a Tris!", size=30, weight=ft.FontWeight.BOLD, color=c["text"], text_align="center"),
                    ft.Divider(height=20, color="transparent"),
                    self.nickname_input, self.error_text, 
                    ft.Container(height=10), self.login_button
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, 
                alignment=ft.MainAxisAlignment.CENTER
            ),
            padding=30, border_radius=20, width=320, 
            bgcolor=c["login_bg"], border=ft.border.all(1, c["login_border"])
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
        self.exit_button.visible = False
        self.close_mobile_overlay()
        
        self.lobby_container = ft.Container(
            content=ft.Column(
                [
                    ft.Icon("sports_esports", size=80, color="blue"),
                    ft.Text(f"Ciao, {self.nickname}!", size=28, weight="bold", color=c["text"], text_align="center"),
                    ft.Text("Lobby principale", color=c["text_dim"]),
                    ft.Divider(height=30, color="transparent"),
                    ft.ElevatedButton(
                        "AVVIA PARTITA", icon="play_circle", width=240, height=55, 
                        style=ft.ButtonStyle(bgcolor="blue", color="white", text_style=ft.TextStyle(size=16, weight="bold")), 
                        on_click=self.start_matchmaking
                    ),
                    ft.Container(height=15),
                    ft.OutlinedButton("Esci (Logout)", icon="logout", on_click=self.request_exit_dialog, width=200)
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, 
                alignment=ft.MainAxisAlignment.CENTER, 
                scroll=ft.ScrollMode.AUTO
            ),
            alignment=ft.alignment.center, expand=True, bgcolor=c["bg"]
        )
        self.main_content_area.content = self.lobby_container
        self.refresh_layout_state()
        self.page.update()

    def show_waiting_view(self):
        self.current_view = "waiting"
        c = self.get_c()
        self.sidebar_area.visible = False
        self.chat_drawer_button.visible = False
        self.close_mobile_overlay()

        self.waiting_container = ft.Container(
            content=ft.Column(
                [
                    ft.ProgressRing(width=50, height=50),
                    ft.Divider(height=20, color="transparent"),
                    ft.Text("Cerco avversario...", size=20, weight="bold", color=c["text"]),
                    ft.Text("Attendi...", color=c["text_dim"]),
                    ft.Divider(height=40, color="transparent"),
                    ft.OutlinedButton("Annulla", icon="close", on_click=self.cancel_matchmaking, style=ft.ButtonStyle(color="red"))
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
        
        self.game_chat_ui["list"].controls.clear()
        self.game_chat_ui["list"].controls.append(ft.Text("Partita iniziata!", color="green", italic=True, size=12))

        self.exit_button.visible = True
        self.close_mobile_overlay()
        
        self.board_items = [] 
        self.status_text = ft.Text(
            f"Tu: {self.my_symbol} (vs {self.opponent})", 
            size=18, weight=ft.FontWeight.BOLD, 
            color="green" if self.my_symbol == "X" else "blue", 
            text_align="center"
        )

        rows = []
        btn_size = 80; img_size = 50

        for r in range(3):
            row_controls = []
            for c in range(3):
                idx = r * 3 + c
                img = ft.Image(src="x.png", opacity=0, width=img_size, height=img_size, fit=ft.ImageFit.CONTAIN)
                btn = ft.ElevatedButton(
                    content=img, 
                    width=btn_size, height=btn_size, 
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=0), 
                    on_click=lambda e, i=idx: self.on_cell_click(i)
                )
                self.board_items.append((btn, img))
                row_controls.append(btn)
            rows.append(ft.Row(controls=row_controls, alignment=ft.MainAxisAlignment.CENTER))

        self.game_container = ft.Container(
            content=ft.Column(
                [
                    self.status_text,
                    ft.Divider(height=10, color="transparent"),
                    ft.Column(controls=rows, spacing=5, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Divider(height=20, color="transparent"),
                    ft.OutlinedButton("Arrenditi", icon="flag", on_click=self.request_abandon_match_dialog, style=ft.ButtonStyle(color="red"))
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, 
                alignment=ft.MainAxisAlignment.CENTER, 
                scroll=ft.ScrollMode.AUTO
            ),
            alignment=ft.alignment.center, expand=True, bgcolor=self.get_c()["bg"]
        )
        self.main_content_area.content = self.game_container
        self.refresh_layout_state()
        self.page.update()

    def show_end_dialog(self, result):
        title_text = "FINE"; msg_text = ""; text_color = "white"
        if "disconnected" in result: 
            title_text = "VITTORIA"; msg_text = "Avversario ritirato"; text_color = "green"
        elif result == "draw": 
            title_text = "PAREGGIO"; msg_text = "Nessun vincitore"; text_color = "orange"
        elif result == f"{self.my_symbol}_wins": 
            title_text = "VITTORIA!"; msg_text = "Ben fatto!"; text_color = "green"
        else: 
            title_text = "SCONFITTA"; msg_text = "Ritenta!"; text_color = "red"

        c = self.get_c()
        self.end_container = ft.Container(
            content=ft.Column(
                [
                    ft.Text(title_text, size=35, weight="bold", color=text_color),
                    ft.Text(msg_text, size=18, color=c["text"]),
                    ft.Divider(height=30, color="transparent"),
                    ft.ElevatedButton(
                        "Rigioca", icon="refresh", on_click=self.start_matchmaking, 
                        width=200, height=50, style=ft.ButtonStyle(bgcolor="green", color="white")
                    ),
                    ft.Container(height=10),
                    ft.TextButton(
                        "Torna in Lobby", icon="home", on_click=self.return_to_lobby, 
                        style=ft.ButtonStyle(color="grey")
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER
            ),
            alignment=ft.alignment.center, expand=True, bgcolor=c["bg"]
        )
        self.main_content_area.content = self.end_container
        self.page.update()

    # --- CONNESSIONE E LOGICA ---
    def start_matchmaking(self, e): 
        self.client.send({"action": "start_search"})
        self.show_waiting_view()

    def cancel_matchmaking(self, e): 
        self.client.send({"action": "leave_queue"})
        self.show_lobby_view()

    def return_to_lobby(self, e):
        self.client.send({"action": "back_to_lobby"})
        self.show_lobby_view()

    def on_cell_click(self, idx):
        self.client.send({
            "action": "move", 
            "player_id": self.nickname, 
            "room_id": self.room_id, 
            "pos": idx
        })
    
    def update_board(self, board, turn, result=None):
        if self.current_view != "game" or not self.board_items: 
            return
        
        for i, val in enumerate(board):
            if i >= len(self.board_items): 
                break
            btn, img = self.board_items[i]
            
            if val == "X": 
                img.src = "x.png"; img.opacity = 1
            elif val == "O": 
                img.src = "o.png"; img.opacity = 1
            else: 
                img.src = "x.png"; img.opacity = 0
            
            is_my_turn = (turn == self.my_symbol)
            is_empty = (val is None)
            game_running = (turn is not None)
            btn.disabled = not (is_my_turn and is_empty and game_running)
        
        if self.status_text:
            if turn: 
                self.status_text.value = f"Tu: {self.my_symbol} - {'Tocca a te!' if turn == self.my_symbol else f'Tocca a {self.opponent}'}"
            else: 
                self.status_text.value = "Partita Terminata"
        self.page.update()

    def on_connect(self, e):
        self.error_text.visible = False
        self.expecting_disconnect = False
        self.page.update()
        
        nick_val = self.nickname_input.value.strip()
        if not nick_val or len(nick_val) < 3 or len(nick_val) > 15 or not re.match(r"^[a-zA-Z0-9]+$", nick_val):
            self.error_text.value = "Nickname non valido (3-15 caratteri alfanumerici)."
            self.error_text.visible = True
            self.page.update()
            return
            
        self.nickname = nick_val
        self.login_button.disabled = True
        self.login_button.text = "Connessione..."
        self.nickname_input.disabled = True
        self.page.update()
        
        if self.client.sock: 
            try: self.client.sock.close() 
            except: pass
        self.client.connected = False
        self.client.sock = None
        
        try:
            self.client.connect()
            self.client.register_callback(self.handle_server_message)
            self.client.send({"action": "join", "player_id": self.nickname})
        except Exception as ex: 
            self.nickname_input.disabled = False
            self._handle_login_error(f"Errore: {ex}")

    def _handle_login_error(self, reason):
        self.error_text.value = reason
        self.error_text.visible = True
        self.login_button.disabled = False
        self.login_button.text = "Entra in Lobby"
        self.nickname_input.disabled = False
        self.page.update()

    def handle_server_message(self, msg):
        try: 
            self._process_message(msg)
        except Exception as e: 
            print(f"UI Error: {e}")

    def _process_message(self, msg):
        msg_type = msg.get("type")
        
        if msg_type == "connection_lost": 
            if not self.expecting_disconnect: 
                self.show_crash_dialog()
            return
        
        if msg_type == "chat_message": 
            self.add_chat_message(msg["data"]["sender"], msg["data"]["message"])
            return
        
        if msg_type == "player_list_update": 
            self.online_players = msg["data"]
            self.update_players_list_ui()
            return
        
        if msg_type == "match_found":
            self.room_id = msg["data"]["game_id"]
            self.my_symbol = msg["data"]["you_are"]
            self.opponent = msg["data"]["opponent"]
            self.show_game_view()
            return
        
        if msg_type == "game_state":
            data = msg["data"]
            self.update_board(data["board"], data["turn"], result=data.get("result"))
            if data.get("status") == "ended": 
                self.show_end_dialog(data["result"])
            return
        
        if self.current_view == "login":
            if msg.get("ok") is False: 
                self.expecting_disconnect = True
                self._handle_login_error(msg.get("reason"))
            elif msg.get("ok") is True: 
                self.show_lobby_view()

    def update_players_list_ui(self):
        self.players_list_view.controls.clear()
        for p in self.online_players:
            status_color = "green" if p['status'] == 'online' else "orange" if p['status'] == 'waiting' else "red"
            is_me = "(Tu)" if p['name'] == self.nickname else ""
            self.players_list_view.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Container(width=10, height=10, border_radius=10, bgcolor=status_color), 
                        ft.Column([
                            ft.Text(f"{p['name']} {is_me}", weight="bold", size=13), 
                            ft.Text(p['status'], size=10, color="grey")
                        ], spacing=2)
                    ]), 
                    padding=5
                )
            )
        self.page.update()

    def add_chat_message(self, sender, text):
        c = self.get_c()
        color = c["me"] if sender == self.nickname else c["other"]
        target = self.lobby_chat_ui["list"] if self.current_view == "lobby" else self.game_chat_ui["list"]
        target.controls.append(
            ft.Column([
                ft.Text(sender, size=10, color="grey", weight="bold"), 
                ft.Text(text, size=13, color=color, selectable=True)
            ], spacing=2)
        )
        self.page.update()

    def send_chat_message(self, e, input_field):
        text = input_field.value.strip()
        if text: 
            input_field.value = ""
            self.page.update()
            self.client.send({"action": "chat", "message": text})
            input_field.focus()

    def _animation_loop(self):
        t = 0
        while self.anim_running:
            try:
                h = self.page.height if self.page.height else 800
                w = self.page.width if self.page.width else 600
                t += 0.05
                for i, obj in enumerate(self.background_objs):
                    obj['y'] += obj['speed']
                    wave_offset = obj['amplitude'] * math.sin(t + i)
                    obj['control'].top = obj['y']
                    obj['control'].left = obj['base_x'] + wave_offset
                    if obj['y'] > h: 
                        obj['y'] = -50
                        obj['base_x'] = random.randint(0, int(w))
                self.page.update()
                time.sleep(0.02)
            except: break

    def start_background_animation(self):
        self.anim_running = True
        self.background_objs = []
        for _ in range(30):
            self.background_objs.append({
                'control': ft.Image(src=random.choice(["x.png", "o.png"]), width=random.randint(20,40), opacity=0.3, fit=ft.ImageFit.CONTAIN, left=0, top=0), 
                'speed': random.uniform(1,3), 
                'y': float(random.randint(-800,0)), 
                'base_x': float(random.randint(0,1000)), 
                'amplitude': random.randint(20,60)
            })
        threading.Thread(target=self._animation_loop, daemon=True).start()

    def stop_animation(self):
        self.anim_running = False

    def request_exit_dialog(self, e):
        self.current_dialog = ft.AlertDialog(
            modal=True, title=ft.Text("Esci"), content=ft.Text("Uscire?"), 
            actions=[
                ft.TextButton("No", on_click=self.close_dialog), 
                ft.TextButton("Si", on_click=self.logout, style=ft.ButtonStyle(color="red"))
            ]
        )
        self.page.open(self.current_dialog)

    def request_abandon_match_dialog(self, e):
        self.current_dialog = ft.AlertDialog(
            modal=True, title=ft.Text("Resa"), content=ft.Text("Arrendersi?"), 
            actions=[
                ft.TextButton("No", on_click=self.close_dialog), 
                ft.TextButton("Si", on_click=self.confirm_abandon, style=ft.ButtonStyle(color="red"))
            ]
        )
        self.page.open(self.current_dialog)

    def confirm_abandon(self, e):
        self.close_dialog(e)
        if self.room_id:
            self.client.send({"action": "leave_game", "room_id": self.room_id})
        self.room_id = None
        self.my_symbol = None
        self.opponent = None
        self.board_items = []
        self.show_lobby_view()

    def show_crash_dialog(self):
        self.stop_animation()
        if self.current_dialog: 
            try: self.page.close(self.current_dialog)
            except: pass
        self.current_dialog = ft.AlertDialog(
            modal=True, title=ft.Text("Errore"), content=ft.Text("Disconnesso."), 
            actions=[ft.ElevatedButton("Login", on_click=self.logout)]
        )
        self.page.open(self.current_dialog)
    
    def close_dialog(self, e):
        if self.current_dialog:
            self.page.close(self.current_dialog)
            self.current_dialog = None
    
    def logout(self, e):
        if self.current_dialog: 
            self.page.close(self.current_dialog)
        if self.client.sock: 
            try: self.client.sock.close() 
            except: pass
        self.client.connected = False; self.show_login()
