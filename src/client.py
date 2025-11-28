# client/client.py

import socket
import threading
from protocollo import send_msg, recv_msg  

class TrisClient:
    def __init__(self, host='127.0.0.1', port=5000):
        self.host = host
        self.port = port
        self.sock = None
        self.connected = False
        self.callback = None
        self.receive_thread = None

    def connect(self):
        """Tenta la connessione al server."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self.connected = True
        
        # Avvia il thread di ascolto
        self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.receive_thread.start()

    def register_callback(self, callback_func):
        """Collega la funzione GUI per ricevere aggiornamenti."""
        self.callback = callback_func

    def send(self, data):
        """Invia dati usando la funzione condivisa send_msg."""
        if not self.sock or not self.connected:
            return

        try:
            # Usa direttamente la funzione del protocollo
            send_msg(self.sock, data)
        except Exception as e:
            print(f"[CLIENT] Errore invio (send_msg): {e}")
            self._handle_disconnect()

    def _receive_loop(self):
        """Loop che usa recv_msg per leggere i pacchetti completi."""
        while self.connected and self.sock:
            try:
                # recv_msg è bloccante e gestisce header + payload
                message = recv_msg(self.sock)
                
                if self.callback:
                    self.callback(message)

            except Exception as e:
                # Se recv_msg fallisce (connessione chiusa o errore protocollo), usciamo
                if self.connected: 
                    print(f"[CLIENT] Disconnessione o errore ricezione: {e}")
                break
        
        self._handle_disconnect()

    def _handle_disconnect(self):
        """Pulisce la connessione e avvisa la GUI."""
        if self.connected:
            print("[CLIENT] Chiusura connessione.")
            self.connected = False
            if self.sock:
                try: self.sock.close()
                except: pass
            self.sock = None
            
            # Avvisa la GUI
            if self.callback:
                self.callback({"type": "connection_lost"})
