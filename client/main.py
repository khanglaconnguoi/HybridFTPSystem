import socket

HOST = "127.0.0.1"
PORT = 21

try:
    print("[Connecting to server...]\n")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((HOST, PORT))
    print("[Connected to server]\n")

    response = s.recv(1024)
    print("[Server response]\n", response.decode("utf8"), "\n")

except ConnectionRefusedError:
    print("[Error connecting] Server refused connection\n")
    exit(1)

except Exception as e:
    print("[Error connecting]\n", e, "\n")
    exit(1)

try:
    while True:
        raw_command = input("[Enter command]\n> ")
        print()
        if raw_command.lower() == "exit":
            print("[Disconnecting...]\n")
            break
        s.sendall(raw_command.encode("utf-8"))

        response = s.recv(1024)
        print("[Server response]\n", response.decode("utf8"), "\n")

except ConnectionResetError:
    print("[Server disconnected]\n")

except KeyboardInterrupt:
    print("[Disconnecting...]\n")

finally:
    s.close()
    print("[Client shutting down]\n")


# from client.tcp_control import TcpControlClient

# HOST = "127.0.0.1"
# PORT = 21


# def main() -> None:
#     client = TcpControlClient(HOST, PORT)
#     banner = client.connect()
#     print(banner)

#     try:
#         while True:
#             raw = input("> ").strip()
#             if not raw:
#                 continue
#             reply = client.send_command(raw)
#             print(reply)
#             if raw.upper().startswith("QUIT"):
#                 break
#     except KeyboardInterrupt:
#         pass
#     finally:
#         client.close()


# if __name__ == "__main__":
#     main()
