import socket
import threading

def ricevi(sock):
    while True:
        try:
            msg = sock.recv(1024).decode('utf-8')
            if not msg:
                break
            print(msg)
        except:
            break

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(('127.0.0.1', 12345))

nickname = input("Scegli un nickname: ")
client.sendall(nickname.encode('utf-8'))

thread = threading.Thread(target=ricevi, args=(client,))
thread.start()

while True:
    msg = input()
    client.sendall(msg.encode('utf-8'))
    if msg.lower() == "exit":
        break

client.close()
