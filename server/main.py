import socket

HOST = "127.0.0.1"
PORT = 21

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind((HOST, PORT))
s.listen(1)

print("[Waiting for client...]\n")
conn, addr = s.accept()

try:
    print(f"[Connected by {addr}]\n")
    while True:
        data = conn.recv(1024)
        if len(data) == 0:
            print("[Client disconnected. Disconnecting...]\n")
            break

        print("[Command received]\n", data.decode("utf8"), "\n")

except ConnectionResetError:
    print("[Client disconnected. Disconnecting...]\n")

except KeyboardInterrupt:
    print("[Disconnecting...]\n")

finally:
    conn.close()
    s.close()
    print("[Server shutting down]\n")
