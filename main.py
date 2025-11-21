# client/main.py

import flet as ft
from client import TrisClient
import warnings
import time

# Ignora warning deprecazione
warnings.filterwarnings("ignore")

class TrisFletUI:
    def __init__(self, page: ft.Page):
        self.page = page
        self.client = TrisClient() 
        self.nickname = None
        self.room_id = None
        self.my_symbol = None
        self.opponent = None
        self.board_buttons = []
        self.status_text = None
        
        # Riferimenti ai controlli del login per poterli riattivare in caso di errore
        self.login_button = None
        self.nickname_input = None

        self.page.title = "Tris Multiplayer - Ture Pagans"
        self.page.vertical_alignment = ft.MainAxisAlignment.CENTER
        self.page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.page.theme_mode = ft.ThemeMode.DARK 

        self.show_login()

    def show_login(self):
        """Mostra la schermata di login con limite caratteri fisico"""
        self.page.controls.clear()
        self.page.dialog = None 
        
        default_nick = self.nickname if self.nickname else ""
        
        self.nickname_input = ft.TextField(
            label="Nickname", 
            width=200, 
            text_align=ft.TextAlign.CENTER,
            value=default_nick,
            on_submit=self.on_connect,
            
            # --- MODIFICA QUI ---
            max_length=15  # Blocca la scrittura dopo 12 caratteri
            # --------------------
        )
        
        self.error_text = ft.Text(
            value="", 
            color="red", 
            size=14, 
            weight=ft.FontWeight.BOLD,
            visible=False,
            text_align=ft.TextAlign.CENTER
        )
        
        self.login_button = ft.ElevatedButton(
            "Connetti", 
            on_click=self.on_connect, 
            width=150
        )
        
        self.page.add(
            ft.Column(
                [
                    ft.Text("Benvenuto a Tris!", size=30, weight=ft.FontWeight.BOLD),
                    ft.Divider(height=20, color="transparent"),
                    self.nickname_input,
                    self.error_text, 
                    ft.Container(height=10), 
                    self.login_button
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER
            )
        )
        self.page.update()

    def on_connect(self, e):
        """Gestisce il click sul tasto Connetti"""
        
        # 1. RESET: Nascondi l'errore e fai "salire" il bottone
        self.error_text.visible = False
        self.error_text.value = ""
        self.page.update()

        # .strip() rimuove gli spazi iniziali e finali
        # Quindi se l'utente scrive "   ", diventa "" (stringa vuota)
        nick_val = self.nickname_input.value.strip()
        
        # --- CONTROLLI CLIENT ---
        error_msg = None
        
        # 1. Controllo VUOTO (Nuovo)
        if not nick_val:
            error_msg = "Il nickname non può essere vuoto."
            
        # 2. Controllo LUNGHEZZA MINIMA
        elif len(nick_val) < 3:
            error_msg = "Nickname troppo corto (min 3)."
            
        # 3. Controllo LUNGHEZZA MASSIMA (ridondante con max_length, ma sicuro)
        elif len(nick_val) > 15:
            error_msg = "Nickname troppo lungo (max 15)."
            
        # 4. Controllo CARATTERI (Solo lettere e numeri)
        elif not nick_val.isalnum():
            error_msg = "Usa solo lettere e numeri."
            
        # Se abbiamo trovato un errore locale:
        if error_msg:
            self.error_text.value = error_msg
            self.error_text.visible = True # Mostra l'errore e sposta il bottone
            self.page.update()
            return
        # ------------------------

        self.nickname = nick_val
        
        # Disabilita UI se tutto è OK
        self.login_button.disabled = True
        self.login_button.text = "Connessione..."
        self.nickname_input.disabled = True
        self.page.update()

        self._perform_connection()

    def _show_error(self, message):
        """Mostra una barra rossa con l'errore"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message, color="white"), 
            bgcolor="red"
        )
        self.page.snack_bar.open = True
        self.page.update()

    def _perform_connection(self):
        """Avvia socket e invia login, ma NON cambia ancora la UI"""
        if self.client.sock:
            try:
                self.client.sock.close()
            except:
                pass
        self.client.connected = False
        self.client.sock = None

        # Connessione al server
        try:
            self.client.connect()
            self.client.register_callback(self.handle_server_message)
            # Invio messaggio di Login
            self.client.send({"action": "join", "player_id": self.nickname})
        except Exception as e:
            # Se fallisce proprio la connessione al socket (server spento)
            self._handle_login_error(f"Impossibile connettersi al server: {e}")

    def _handle_login_error(self, reason):
        """Gestisce gli errori del Server"""
        print(f"[GUI] Errore Login: {reason}")
        
        # Mostra l'errore e sposta il bottone
        self.error_text.value = reason
        self.error_text.visible = True # <-- Spinge giù il bottone
        
        # Riabilita i controlli
        if self.login_button:
            self.login_button.disabled = False
            self.login_button.text = "Connetti"
        if self.nickname_input:
            self.nickname_input.disabled = False
            self.nickname_input.focus()
        
        self.page.update()

    def show_waiting_screen(self):
        """Mostra la schermata di attesa (chiamata SOLO se login OK)"""
        self.page.controls.clear()
        self.page.add(
            ft.Column(
                [
                    ft.ProgressRing(),
                    ft.Divider(height=10, color="transparent"),
                    ft.Text(f"Bentornato {self.nickname}!", size=20, weight=ft.FontWeight.BOLD),
                    ft.Text("Cerco un avversario...", size=16)
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER
            )
        )
        self.page.update()

    def handle_server_message(self, msg):
        """Riceve messaggi dal socket e aggiorna la UI"""
        # Flet richiede di aggiornare la UI dal thread principale o tramite lock impliciti
        # Di solito funziona bene, ma in casi complessi meglio usare page.run_task o simili.
        # Qui lo teniamo semplice.
        try:
            self._update_ui(msg)
        except Exception as e:
            print(f"[GUI ERROR] Errore aggiornamento UI: {e}")

    def _update_ui(self, msg):
        # --- NUOVA LOGICA GESTIONE RISPOSTE LOGIN ---
        
        # CASO 1: Il server rifiuta il login (ok: False)
        if msg.get("ok") is False:
            reason = msg.get("reason", "Errore sconosciuto")
            # Importante: siamo ancora sulla schermata login, quindi riattiviamo i bottoni
            self._handle_login_error(reason)
            # Chiudiamo il socket lato client per pulizia
            if self.client.sock: self.client.sock.close()
            return

        # CASO 2: Il server accetta il login (ok: True, status: waiting)
        if msg.get("ok") is True and msg.get("status") == "waiting":
            # ORA possiamo cambiare schermata
            self.show_waiting_screen()
            return

        # --------------------------------------------

        msg_type = msg.get("type")
        
        if msg_type == "connection_lost":
            print("[GUI] Connessione persa. Torno al login.")
            # Se perdiamo la connessione, torniamo al login (reset completo)
            self.logout(None)
            return
        
        if msg_type == "match_found":
            self.room_id = msg["data"]["game_id"]
            self.my_symbol = msg["data"]["you_are"]
            self.opponent = msg["data"]["opponent"]
            self.show_game_board()

        elif msg_type == "game_state":
            data = msg["data"]
            status = data.get("status")
            self.update_board(data["board"], data["turn"], result=data.get("result"))
            if status == "ended":
                self.show_end_dialog(data["result"])

    def show_game_board(self):
        """Costruisce e mostra la griglia di gioco"""
        self.page.controls.clear()
        self.board_buttons = []
        
        self.status_text = ft.Text(
            f"Tu sei: {self.my_symbol} (vs {self.opponent})", 
            size=20, 
            weight=ft.FontWeight.BOLD,
            color="green" if self.my_symbol == "X" else "blue"
        )

        rows = []
        for r in range(3):
            row_controls = []
            for c in range(3):
                idx = r * 3 + c
                btn = ft.ElevatedButton(
                    text=" ",
                    width=80,
                    height=80,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        text_style=ft.TextStyle(size=40, weight=ft.FontWeight.BOLD),
                    ),
                    on_click=lambda e, i=idx: self.on_cell_click(i)
                )
                self.board_buttons.append(btn)
                row_controls.append(btn)
            rows.append(ft.Row(controls=row_controls, alignment=ft.MainAxisAlignment.CENTER))

        board_container = ft.Column(
            controls=rows,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10
        )

        self.page.add(
            ft.Column(
                controls=[
                    self.status_text,
                    ft.Divider(height=20, color="transparent"),
                    board_container
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                expand=True 
            )
        )
        self.page.update()

    def update_board(self, board, turn, result=None):
        for i, val in enumerate(board):
            color = "green" if val == "X" else "blue" if val == "O" else "white"
            self.board_buttons[i].content = ft.Text(val if val else " ", color=color, size=30, weight=ft.FontWeight.BOLD)
            self.board_buttons[i].text = val if val else " "
            
            is_my_turn = (turn == self.my_symbol)
            is_empty = (val is None)
            game_running = (turn is not None)
            
            self.board_buttons[i].disabled = not (is_my_turn and is_empty and game_running)
        
        if self.status_text:
            if turn:
                turn_msg = "Tocca a te!" if turn == self.my_symbol else f"Tocca a {self.opponent}"
                self.status_text.value = f"Tu sei: {self.my_symbol} - {turn_msg}"
                self.status_text.color = "white"
            else:
                self.status_text.value = "Partita Terminata"

        self.page.update()

    def on_cell_click(self, idx):
        if not self.room_id: return
        self.client.send({
            "action": "move",
            "player_id": self.nickname,
            "room_id": self.room_id,
            "pos": idx
        })

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

        self.page.controls.clear()
        
        end_screen = ft.Column(
            controls=[
                ft.Text(title_text, size=40, weight=ft.FontWeight.BOLD, color=text_color),
                ft.Divider(height=10, color="transparent"),
                ft.Text(msg_text, size=20),
                ft.Divider(height=40, color="transparent"),
                
                ft.ElevatedButton(
                    text="Gioca di nuovo",
                    icon="refresh",
                    on_click=self.play_again, 
                    width=250,
                    height=50,
                    style=ft.ButtonStyle(bgcolor="green", color="white")
                ),
                ft.Divider(height=10, color="transparent"),
                
                ft.TextButton(
                    text="Cambia Nickname (Esci)",
                    on_click=self.logout, 
                    style=ft.ButtonStyle(color="grey")
                )
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.page.add(end_screen)
        self.page.update()

    def play_again(self, e):
        # Disconnessione pulita
        if self.client.sock:
            try: self.client.sock.close()
            except: pass
        self.client.connected = False
        self.client.sock = None
        self.room_id = None
        self.my_symbol = None
        self.opponent = None

        # Schermata transitoria
        self.page.controls.clear()
        pb = ft.ProgressBar(width=200, color="amber")
        status_txt = ft.Text("Riavvio server in corso...", size=16)
        
        self.page.add(
            ft.Column(
                [
                    ft.Text("Preparazione nuova partita", size=24, weight=ft.FontWeight.BOLD),
                    ft.Divider(height=20, color="transparent"),
                    pb,
                    ft.Divider(height=10, color="transparent"),
                    status_txt
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            )
        )
        self.page.update()

        # Delay tattico per pulizia server
        import time
        for i in range(15):
            time.sleep(0.1)
        
        status_txt.value = "Connessione in corso..."
        self.page.update()
        
        # Si riconnette usando il vecchio nickname senza passare dal login
        self._perform_connection()

    def logout(self, e):
        if self.client.sock:
            try: self.client.sock.close()
            except: pass
        self.client.connected = False
        self.client.sock = None
        
        self.show_login()

def main(page: ft.Page):
    TrisFletUI(page)

ft.app(target=main)
