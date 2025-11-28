import flet as ft
import time
import random
import threading
import math
import re
import warnings
from client import TrisClient
from settings import APP_COLORS

warnings.filterwarnings("ignore")

class TrisFletUI:
    def __init__(self, page: ft.Page):
        self.page = page
        self.client = TrisClient()
        self.page.window.icon = "icon.ico"

        # Dati Utente
        self.nickname = None
        self.room_id = None
        self.my_symbol = None
        self.opponent = None

        # Stato Grafico
        self.current_view = "login"
        self.colors = APP_COLORS
        self.is_mobile = False

        # Gestione Inviti
        self.inviting_target = None      
        self.invite_timer_running = False 

        # Gestione Errori/Connessione
        self.expecting_disconnect = False

        # CREAZIONE DELLE DUE CHAT
        self.lobby_chat_ui = self._build_chat_components("LOBBY CHAT")
        self.game_chat_ui = self._build_chat_components("GAME CHAT")

        # Lista giocatori e ListView
        self.online_players = []
        self.players_list_view = ft.ListView(expand=True, spacing=5, padding=5)

        # Riferimenti UI Dinamici
        self.btn_matchmaking = None 

        # Setup Pagina
        self.page.title = "Tris Python Socket by Giuffrida - Romeo - Scandurra"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = self.get_c()["bg"]
        self.page.padding = 0
        self.page.on_resized = self.on_page_resize

        # Animazione
        self.anim_running = False
        self.background_objs = []
        self.current_dialog = None
        self.board_items = []
        self.status_text = None

        #   CONTAINER PRINCIPALI  
        self.main_content_area = ft.Container(expand=True, padding=10)
        
        self.sidebar_area = ft.Container(
            width=300, 
            visible=False, 
            animate_opacity=300, 
            bgcolor=self.get_c()["sidebar"],
            border=ft.border.only(left=ft.border.BorderSide(1, "#444"))
        )

        self.mobile_overlay = ft.Container(
            visible=False,
            expand=True,
            bgcolor=self.get_c()["sidebar"],
            padding=0,
            offset=ft.Offset(1, 0), 
            animate_offset=ft.Animation(300, ft.AnimationCurve.EASE_OUT),
        )

        #   NAVBAR 
        self.exit_button = ft.IconButton(
            icon="exit_to_app", tooltip="Esci", visible=False, on_click=self.request_exit_dialog
        )
        self.chat_drawer_button = ft.IconButton(
            icon="chat", tooltip="Apri Chat", visible=False, on_click=self.toggle_mobile_overlay
        )

        self.page.appbar = ft.AppBar(
            leading=self.exit_button,
            leading_width=40, 
            title=ft.Row(
                [
                    ft.Image(src="icon.png", width=30, height=30, fit=ft.ImageFit.CONTAIN),
                    ft.Text("Tris Python Socket", weight=ft.FontWeight.BOLD),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=10
            ),
            center_title=True,
            bgcolor="blueGrey900",
            actions=[self.chat_drawer_button, ft.Container(width=10)]
        )

        #   LAYOUT PRINCIPALE  
        self.page.add(
            ft.Stack(
                controls=[
                    ft.Row(controls=[self.main_content_area, self.sidebar_area], expand=True, spacing=0),
                    self.mobile_overlay
                ],
                expand=True
            )
        )

        self.check_responsive_layout()
        self.show_login()

    def get_c(self):
        return self.colors["dark"]

    def _build_chat_components(self, title):
        c = self.get_c()
        msg_list = ft.ListView(expand=True, spacing=5, auto_scroll=True, padding=10)
        list_container = ft.Container(content=msg_list, expand=True, bgcolor="#121212")
        inp = ft.TextField(
            hint_text="Scrivi messaggio...", text_size=12, height=45, content_padding=10,
            on_submit=lambda e: self.send_chat_message(e, inp),
            bgcolor=c["input_bg"], color=c["input_fg"], border_color=c["border"], expand=True
        )
        header = ft.Container(content=ft.Text(title, weight="bold", size=14, color=c["text"]), padding=10, bgcolor=c["surface"])
        inp_container = ft.Container(content=ft.Row([inp, ft.IconButton("send", icon_size=20, on_click=lambda e: self.send_chat_message(e, inp))]), padding=5, bgcolor=c["surface"])
        return {"list": msg_list, "header": header, "list_container": list_container, "input_container": inp_container}

    #   RESPONSIVITÀ  
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
        if self.is_mobile:
            self.sidebar_area.visible = False
            self.chat_drawer_button.visible = (self.current_view in ["lobby", "game"])
        else:
            self.sidebar_area.visible = (self.current_view == "lobby")
            self.chat_drawer_button.visible = (self.current_view == "game")
            self.mobile_overlay.offset = ft.Offset(1, 0)
            self.mobile_overlay.visible = False
            if self.current_view == "lobby":
                self.sidebar_area.content = self.build_sidebar_content(for_mobile=False)

    def toggle_mobile_overlay(self, e):
        if self.mobile_overlay.offset.x == 1:
            content = self.build_sidebar_content(for_mobile=True)
            self.mobile_overlay.content = content
            self.mobile_overlay.visible = True
            self.mobile_overlay.offset = ft.Offset(0, 0)
        else:
            self.mobile_overlay.offset = ft.Offset(1, 0)
        self.page.update()

    def close_mobile_overlay(self):
        if self.mobile_overlay.visible:
            self.mobile_overlay.offset = ft.Offset(1, 0)
            self.page.update()

    #   COSTRUZIONE SIDEBAR  
    def build_sidebar_content(self, for_mobile=False):
        c = self.get_c()
        chat_ui = self.lobby_chat_ui if self.current_view == "lobby" else self.game_chat_ui
        controls_list = []

        if for_mobile:
            controls_list.append(ft.Container(content=ft.Row([ft.Text("Menu", weight="bold", size=16), ft.IconButton(ft.icons.CLOSE, on_click=self.toggle_mobile_overlay)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), padding=10, bgcolor=c["surface"]))

        if self.current_view == "lobby":
            controls_list.append(ft.Container(content=ft.Text("GIOCATORI ONLINE", weight="bold", size=14, color=c["text"]), padding=10, bgcolor=c["surface"]))
            controls_list.append(ft.Container(content=self.players_list_view, height=200, bgcolor="#121212", padding=0))
            controls_list.append(ft.Divider(height=1, thickness=1, color="grey"))

        controls_list.append(chat_ui["header"])
        controls_list.append(chat_ui["list_container"]) 
        controls_list.append(chat_ui["input_container"])

        return ft.Column(controls=controls_list, spacing=0, expand=True)

    #   LOGICA INVITI  
    def send_invite(self, target_player):
        if self.inviting_target: return
        self.inviting_target = target_player
        self.invite_timer_running = True
        
        if self.btn_matchmaking:
            self.btn_matchmaking.disabled = True
            self.btn_matchmaking.text = f"In attesa di {target_player}..."
            self.btn_matchmaking.update()
            
        self.client.send({"action": "send_invite", "target_id": target_player})
        threading.Thread(target=self._invite_timeout_loop, daemon=True).start()

    def _invite_timeout_loop(self):
        count = 15
        while count > 0 and self.invite_timer_running and self.current_view == "lobby":
            time.sleep(1)
            count -= 1
        
        if self.invite_timer_running and self.current_view == "lobby":
            self.invite_timer_running = False
            self.inviting_target = None
            self._reset_matchmaking_button()
            self.show_toast(f"Nessuna risposta dall'utente.")

    def _reset_matchmaking_button(self):
        if self.btn_matchmaking:
            self.btn_matchmaking.text = "AVVIA MATCHMAKING"
            self.btn_matchmaking.disabled = False
            self.btn_matchmaking.update()

    def show_toast(self, message, color="orange"):
        self.page.snack_bar = ft.SnackBar(ft.Text(message), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    def show_invite_dialog(self, sender):
        def accept_invite(e):
            self.client.send({"action": "respond_invite", "target_id": sender, "response": "accept"})
            self.page.close(dlg)

        def decline_invite(e):
            self.client.send({"action": "respond_invite", "target_id": sender, "response": "decline"})
            self.page.close(dlg)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Invito ricevuto"),
            content=ft.Text(f"L'utente {sender} vuole giocare con te."),
            actions=[
                ft.TextButton("Rifiuta", on_click=decline_invite, style=ft.ButtonStyle(color="red")),
                ft.ElevatedButton("Accetta", on_click=accept_invite, style=ft.ButtonStyle(bgcolor="green", color="white")),
            ],
        )
        self.page.open(dlg)

    #   VISTE  
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
        
        self.error_text = ft.Text(value="", color="red", size=14, weight=ft.FontWeight.BOLD, visible=False, text_align=ft.TextAlign.CENTER)
        self.login_button = ft.ElevatedButton("Entra in Lobby", on_click=self.on_connect, width=150)
        
        self.login_box_container = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Benvenuto a Tris!", size=30, weight=ft.FontWeight.BOLD, color=c["text"], text_align="center"),
                    ft.Divider(height=20, color="transparent"),
                    self.nickname_input, self.error_text, 
                    ft.Container(height=10), self.login_button
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER
            ),
            padding=30, border_radius=20, width=320, bgcolor=c["login_bg"], border=ft.border.all(1, c["login_border"])
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
        
        self.inviting_target = None
        self.invite_timer_running = False
        
        self.btn_matchmaking = ft.ElevatedButton(
            "AVVIA MATCHMAKING", 
            icon="play_circle", width=250, height=60, 
            style=ft.ButtonStyle(bgcolor="blue", color="white", text_style=ft.TextStyle(size=18, weight="bold")), 
            on_click=self.start_matchmaking
        )

        self.lobby_container = ft.Container(
            content=ft.Column(
                [
                    ft.Icon("sports_esports", size=80, color="blue"),
                    ft.Text(f"Benvenuto, {self.nickname}!", size=30, weight="bold", color=c["text"], text_align="center"), 
                    ft.Text("Sei nella Lobby principale.", color=c["text_dim"]),
                    ft.Divider(height=40, color="transparent"),
                    self.btn_matchmaking, 
                    ft.Container(height=20),
                    ft.OutlinedButton("Esci (Logout)", icon="logout", on_click=self.request_exit_dialog)
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

        self.invite_timer_running = False
        self.game_chat_ui["list"].controls.clear()
        self.game_chat_ui["list"].controls.append(ft.Text("Inizio Partita! Buona fortuna.", color="green", italic=True, size=12))
        self.exit_button.visible = True
        
        self.close_mobile_overlay()
        
        self.board_items = [] 
        self.status_text = ft.Text(
            f"Tu sei: {self.my_symbol} (vs {self.opponent})", 
            size=20, weight=ft.FontWeight.BOLD, 
            color="green" if self.my_symbol == "X" else "blue", 
            text_align="center"
        )

        rows = []
        btn_size = 90
        img_size = 60

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
                    ft.Divider(height=20, color="transparent"),
                    ft.Column(controls=rows, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Divider(height=30, color="transparent"),
                    ft.OutlinedButton("Abbandona Partita", icon="flag", on_click=self.request_abandon_match_dialog, style=ft.ButtonStyle(color="red"))
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
        title_text = "PARTITA FINITA"; msg_text = ""; text_color = "white"
        
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

        c = self.get_c()
        self.end_container = ft.Container(
            content=ft.Column(
                [
                    ft.Text(title_text, size=40, weight="bold", color=text_color),
                    ft.Text(msg_text, size=20, color=c["text"]),
                    ft.Divider(height=40, color="transparent"),
                    ft.ElevatedButton(
                        "Gioca di nuovo", icon="refresh", on_click=self.start_matchmaking, 
                        width=250, height=50, style=ft.ButtonStyle(bgcolor="green", color="white")
                    ),
                    ft.Container(height=10),
                    ft.TextButton(
                        "Torna alla Lobby", icon="home", on_click=self.return_to_lobby, 
                        style=ft.ButtonStyle(color="grey")
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER
            ),
            alignment=ft.alignment.center, expand=True, bgcolor=c["bg"]
        )
        self.main_content_area.content = self.end_container
        self.page.update()

    #   CONNESSIONE E LOGICA  
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
                turn_msg = "Tocca a te!" if turn == self.my_symbol else f"Tocca a {self.opponent}"
                self.status_text.value = f"Tu sei: {self.my_symbol} - {turn_msg}"
            else: 
                self.status_text.value = "Partita Terminata"
        self.page.update()

    def on_connect(self, e):
        self.error_text.visible = False
        self.expecting_disconnect = False
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
            self._handle_login_error(f"Errore Server: {ex}")

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
        
        if msg_type == "incoming_invite":
            self.show_invite_dialog(msg.get("from"))
            return
        
        if msg_type == "invite_declined":
            self.invite_timer_running = False
            self._reset_matchmaking_button()
            self.show_toast(f"{msg.get('from')} ha rifiutato l'invito.", "red")
            return
        
        if msg_type == "invite_error":
            self.invite_timer_running = False
            self._reset_matchmaking_button()
            self.show_toast(msg.get("message"), "red")
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
        c = self.get_c()
        sorted_players = sorted(self.online_players, key=lambda p: 0 if p['name'] == self.nickname else 1)

        for p in sorted_players:
            status_color = "grey"; status_text = "Offline"
            if p['status'] == 'online': status_color = "green"; status_text = "In Lobby"
            elif p['status'] == 'waiting': status_color = "orange"; status_text = "In Coda"
            elif p['status'] == 'ingame': status_color = "red"; status_text = "In Partita"
            is_me = "(Tu)" if p['name'] == self.nickname else ""
            
            row_controls = [
                ft.Container(width=10, height=10, border_radius=10, bgcolor=status_color),
                ft.Column([
                    ft.Text(f"{p['name']} {is_me}", weight="bold", size=13, color=c["text"]), 
                    ft.Text(status_text, size=10, color="grey")
                ], spacing=2, expand=True)
            ]
            
            if p['name'] != self.nickname and p['status'] == 'online':
                invite_btn = ft.IconButton(
                    icon=ft.icons.MAIL, 
                    tooltip=f"Invita {p['name']}",
                    icon_size=20,
                    on_click=lambda e, target=p['name']: self.send_invite(target)
                )
                row_controls.append(invite_btn)

            self.players_list_view.controls.append(
                ft.Container(
                    content=ft.Row(row_controls, alignment=ft.MainAxisAlignment.START), 
                    padding=5,
                    border_radius=5,
                    bgcolor=self.colors["dark"]["input_bg"] if is_me else "transparent"
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
            modal=True, title=ft.Text("Conferma Uscita"), content=ft.Text("Vuoi davvero uscire?"), 
            actions=[
                ft.TextButton("No", on_click=self.close_dialog), 
                ft.TextButton("Si, Esci", on_click=self.logout, style=ft.ButtonStyle(color="red"))
            ]
        )
        self.page.open(self.current_dialog)

    def request_abandon_match_dialog(self, e):
        self.current_dialog = ft.AlertDialog(
            modal=True, title=ft.Text("Abbandona Partita"), content=ft.Text("Vuoi arrenderti e tornare alla lobby?"), 
            actions=[
                ft.TextButton("No", on_click=self.close_dialog), 
                ft.TextButton("Si, Abbandona", on_click=self.confirm_abandon, style=ft.ButtonStyle(color="red"))
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
            modal=True, title=ft.Row([ft.Icon("error", color="red"), ft.Text("Errore Server")]), content=ft.Text("Connessione col server persa."), 
            actions=[ft.ElevatedButton("Torna al Login", on_click=self.logout, bgcolor="red")]
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