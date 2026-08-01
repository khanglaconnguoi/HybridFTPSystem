import socket

HOST = "127.0.0.1"
PORT = 21

try:
    print("[Connecting to server...]\n")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((HOST, PORT))
    print("[Connected to server]\n")

except ConnectionRefusedError:
    print("[Cannot connect to server]\n")
    exit(1)

except Exception as e:
    print("[Error connecting]\n", e, "\n")
    exit(1)

try:
    while True:
        message = input("[Enter command]\n> ")
        print()
        if message.lower() == "exit":
            print("[Disconnecting...]\n")
            break
        s.sendall(message.encode("utf-8"))

except ConnectionResetError:
    print("[Server disconnected]\n")

except KeyboardInterrupt:
    print("[Ctrl-C pressed. Disconnecting...]\n")

finally:
    s.close()
    print("[Client shutting down]\n")
