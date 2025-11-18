import socket
import threading
from protocollo import send_msg, recv_msg
import queue

class TrisClient:
    def __init__(self, host="127.0.0.1", port=5000):
        self.host = host
        self.port = port
        self.sock = None
        self.connected = False
        self.callbacks = []
        self.msg_queue = queue.Queue()
        self._recv_thread = None
        self._lock = threading.Lock()

    def connect(self):
        if self.connected:
            return

        try:
            # Connessione SINCRONA (bloccante) per essere sicuri
            # che quando questa funzione ritorna, siamo connessi.
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            self.connected = True
            print("[TrisClient] Connesso al server")
            
            # Avvia il thread di ricezione solo dopo la connessione
            self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
            self._recv_thread.start()
            
        except Exception as e:
            print(f"[TrisClient] Errore di connessione: {e}")
            self.connected = False
            if self.sock:
                self.sock.close()

    def _recv_loop(self):
        try:
            while self.connected:
                msg = None
                try:
                    # Se siamo disconnessi, esci subito
                    if not self.sock: break
                    msg = recv_msg(self.sock)
                except Exception:
                    # Qualsiasi errore di rete -> interrompi
                    break

                if msg is None:
                    print("[TrisClient] Connessione chiusa dal server")
                    # Se il server chiude la connessione mentre eravamo connessi
                    # potrebbe essere il "reset" forzato dalla logica server.
                    # Mettiamo un messaggio speciale in coda.
                    if self.connected:
                        self.msg_queue.put({"type": "connection_lost"})
                    break

                self.msg_queue.put(msg)
                for cb in self.callbacks:
                    try: cb(msg)
                    except: pass

        finally:
            with self._lock:
                if self.sock:
                    try: self.sock.close()
                    except: pass
                    self.sock = None
                self.connected = False

    def send(self, msg):
        if not self.connected or self.sock is None:
            print("[TrisClient] Tentativo di invio senza connessione")
            return
        try:
            with self._lock:
                send_msg(self.sock, msg)
        except Exception as e:
            print(f"[TrisClient] Errore send: {e}")
            self.connected = False
    
    def register_callback(self, callback):
        if callback not in self.callbacks:
            self.callbacks.append(callback)
