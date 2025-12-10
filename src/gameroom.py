import uuid
import time
import threading
import random 

class GameRoomError(Exception):
    pass

class GameRoom:
    def __init__(self, creator_id):
        self.lock = threading.Lock()
        self.id = str(uuid.uuid4())
        self.players = {creator_id: None} 
        
        self.connections = {} 
        self.board = [None] * 9
        self.turn = None
        self.status = "waiting"
        self.move_history = []
        self.created_at = time.time()
        self.ended_at = None

    def add_player(self, player_id, conn):
        with self.lock:
            if player_id in self.players:
                raise GameRoomError("Player already in room")
            if len(self.players) >= 2:
                raise GameRoomError("Room full")
            
            self.players[player_id] = None
            self.connections[player_id] = conn
            
            # --- SORTEGGIO CASUALE ---
            p_ids = list(self.players.keys()) 
            

            random.shuffle(p_ids) 
            
            
            self.players[p_ids[0]] = "X" 
            self.players[p_ids[1]] = "O" 
            
            self.turn = "X" 
            self.status = "running"
            
            print(f"[GameRoom] Sorteggio effettuato: X={p_ids[0]}, O={p_ids[1]}")
            
            return self.players[player_id]

    def apply_move(self, player_id, pos):
        with self.lock:
            if self.status != "running":
                return {"ok": False, "reason": "Game not running"}
            
            if player_id not in self.players:
                return {"ok": False, "reason": "Player not in room"}
            
            player_symbol = self.players[player_id]
            if self.turn != player_symbol:
                return {"ok": False, "reason": "Not your turn"}
            
            if not (0 <= pos < 9) or self.board[pos] is not None:
                return {"ok": False, "reason": "Invalid move"}

            self.board[pos] = player_symbol
            self.move_history.append({"player": player_id, "pos": pos})
            
            # CONTROLLA VINCITORE
            winner = self._check_winner()
            
            if winner:
                self.status = "ended"
                self.ended_at = time.time()
                result = f"{winner}_wins"
                next_turn = None
            elif all(cell is not None for cell in self.board):
                self.status = "ended"
                self.ended_at = time.time()
                result = "draw"
                next_turn = None
            else:
                self.turn = "O" if self.turn == "X" else "X"
                next_turn = self.turn
                result = "running"

            return {
                "ok": True,
                "board": self.board.copy(),
                "turn": next_turn,
                "status": self.status,
                "result": result
            }

    def _check_winner(self):
        lines = [
            (0, 1, 2), (3, 4, 5), (6, 7, 8),
            (0, 3, 6), (1, 4, 7), (2, 5, 8),
            (0, 4, 8), (2, 4, 6)
        ]
        for a, b, c in lines:
            if self.board[a] is not None and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        return None
