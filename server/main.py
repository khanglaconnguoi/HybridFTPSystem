import sys
from pathlib import Path

# ???
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.ftp_server import FtpServer

HOST = "127.0.0.1"
PORT = 21
SANDBOX_ROOT = "./data"


def main() -> None:
    server = FtpServer(HOST, PORT, SANDBOX_ROOT)
    server.start()


if __name__ == "__main__":
    main()
