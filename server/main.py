import sys
import os
import argparse
from pathlib import Path

# Thêm thư mục gốc dự án vào sys.path
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.ftp_server import FtpServer

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 21
DEFAULT_SANDBOX_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "server_data"))


SERVER_BANNER = r"""
===================================================================
    ______ _____ ____     ___   _____   _____  __   ___  
   / ____//_  __// __ \   |__ \ | ____| / ____|/_ | / _ \ 
  / /_     / /  / /_/ /   __/ / |__ \  | |      | || | | |
 / __/    / /  / ____/   / __/   ___) || |____  | || |_| |
/_/      /_/  /_/       |____/  |____/  \_____| |_| \___/ 

                   HYBRID FTP SERVER - ENGINE CLI                  
===================================================================
"""


def main() -> None:
    print(SERVER_BANNER)

    parser = argparse.ArgumentParser(description="Hybrid FTP Server [25C10]")
    parser.add_argument("host_pos", nargs="?", default=None, help="Host IP to bind to (positional)")
    parser.add_argument("port_pos", nargs="?", type=int, default=None, help="Port to bind to (positional)")
    parser.add_argument("--host", type=str, default=None, help="Host IP to bind to")
    parser.add_argument("--port", type=int, default=None, help="Port to bind to")
    parser.add_argument("--sandbox", type=str, default=DEFAULT_SANDBOX_ROOT, help="Sandbox storage directory path")
    args = parser.parse_args()

    host = args.host or args.host_pos or DEFAULT_HOST
    port = args.port or args.port_pos or DEFAULT_PORT
    sandbox_root = args.sandbox or DEFAULT_SANDBOX_ROOT

    # Đảm bảo kho lưu trữ Sandbox tồn tại
    os.makedirs(sandbox_root, exist_ok=True)
    abs_sandbox = os.path.abspath(sandbox_root)

    print(f"[*] Cấu hình Máy chủ Server:")
    print(f"    - Listening Host: {host}")
    print(f"    - Control Port  : {port}")
    print(f"    - Sandbox Root  : {abs_sandbox}\n")

    server = FtpServer(host, port, abs_sandbox)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[*] [SERVER] Đang tắt máy chủ an toàn...")


if __name__ == "__main__":
    main()
