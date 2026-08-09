import sys
import os
import argparse
from pathlib import Path

# Thêm thư mục gốc dự án vào sys.path
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from client.tcp_control import TcpControlClient
from client.fs_client import Display

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 21

CLI_BANNER = r"""
===================================================================
    ______ _____ ____     ___   _____   _____  __   ___  
   / ____//_  __// __ \   |__ \ | ____| / ____|/_ | / _ \ 
  / /_     / /  / /_/ /   __/ / |__ \  | |      | || | | |
 / __/    / /  / ____/   / __/   ___) || |____  | || |_| |
/_/      /_/  /_/       |____/  |____/  \_____| |_| \___/ 

                   HYBRID FTP SYSTEM - CLIENT CLI                  
===================================================================
"""

HELP_MENU = """
[ DANH SÁCH CÁC CÂU LỆNH FTP ĐƯỢC HỖ TRỢ ]
-------------------------------------------------------------------
  Lệnh Xác thực & Hệ thống (Module A):
    USER <username>     : Gửi tên đăng nhập (VD: USER admin)
    PASS <password>     : Gửi mật khẩu (VD: PASS 123456)
    PWD                 : In đường dẫn thư mục hiện tại
    NOOP                : Kiểm tra kết nối với Server (Ping)
    HELP                : Hiển thị bảng hướng dẫn này
    QUIT / EXIT         : Đóng kết nối và thoát CLI

  Lệnh Kênh Dữ liệu & Truyền tải (Module B):
    TYPE <A/I>          : Thiết lập kiểu truyền (A: ASCII, I: Binary)
    MODE <S/B/C>        : Thiết lập chế độ truyền (Stream/Block/Compressed)
    PASV                : Chuyển sang chế độ Passive Mode (UDP)
    PORT <ip,p1,p2>     : Chuyển sang chế độ Active Mode (UDP)
    RETR <filename>     : Tải tệp tin từ Server về Client (Download)
    STOR <filename>     : Tải tệp tin từ Client lên Server (Upload)
    ABOR                : Hủy bỏ tiến trình truyền dữ liệu đang chạy

  Lệnh Quản lý Tập tin & Thư mục (Module C):
    CWD <path>          : Chuyển thư mục (VD: CWD /storage)
    CDUP                : Nhảy lên thư mục cha
    MKD <dirname>       : Tạo thư mục mới (VD: MKD docs)
    RMD <dirname>       : Xóa thư mục rỗng (VD: RMD docs)
    LIST [path]         : Liệt kê chi tiết thư mục (ls -l)
    NLST [path]         : Liệt kê tên các tập tin (ls)
    SIZE <filename>     : Lấy độ lớn tệp tin theo Bytes
    MDTM <filename>     : Lấy mốc thời gian sửa đổi (YYYYMMDDHHMMSS)
    STOU [filename]     : Giữ chỗ sinh tên tệp độc nhất (Store Unique)
    APPE <filename>     : Chuẩn bị nối dữ liệu vào tệp (Append)
    DELE <filename>     : Xóa tập tin trên Server
    RNFR <oldname>      : Bước 1 đổi tên - Chọn tệp nguồn
    RNTO <newname>      : Bước 2 đổi tên - Đặt tên mới
    HASH <file> [algo]  : Tính mã băm SHA256 / MD5 của tệp
-------------------------------------------------------------------
"""


def main() -> None:
    print(CLI_BANNER)

    parser = argparse.ArgumentParser(description="Hybrid FTP Client [25C10]")
    parser.add_argument("host_pos", nargs="?", default=None, help="Server IP to connect to (positional)")
    parser.add_argument("port_pos", nargs="?", type=int, default=None, help="Server port to connect to (positional)")
    parser.add_argument("--host", type=str, default=None, help="Server IP to connect to")
    parser.add_argument("--port", type=int, default=None, help="Server port to connect to")
    args = parser.parse_args()

    host = args.host or args.host_pos or DEFAULT_HOST
    port = args.port or args.port_pos or DEFAULT_PORT

    print(f"[*] Đang kết nối tới FTP Server {host}:{port}...")
    client = TcpControlClient(host, port)

    try:
        banner = client.connect()
        Display.reply("CONNECT", banner)
    except ConnectionRefusedError:
        print(f"[X] LỖI: Server từ chối kết nối tại {host}:{port}. Vui lòng bật server/main.py trước!\n")
        sys.exit(1)
    except Exception as err:
        print(f"[X] LỖI KẾT NỐI: {err}\n")
        sys.exit(1)

    print("[i] Gõ 'HELP' để xem danh sách câu lệnh. Gõ 'QUIT' để thoát.\n")

    try:
        while True:
            try:
                raw_input_str = input("ftp> ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n[*] Phát hiện tín hiệu ngắt (Ctrl+C). Đang đóng kết nối...")
                break

            if not raw_input_str:
                continue

            cmd_upper = raw_input_str.upper()

            if cmd_upper == "HELP":
                print(HELP_MENU)
                continue

            if cmd_upper in ("QUIT", "EXIT"):
                try:
                    client.quit()
                except Exception:
                    pass
                print("[*] Đã ngắt kết nối an toàn. Cảm ơn bạn đã sử dụng Hybrid FTP CLI!")
                break

            try:
                replies = client.send_command(raw_input_str)
                parts = raw_input_str.split(" ", 1)
                verb = parts[0].upper()
                for reply in replies:
                    Display.reply(verb, reply)

            except Exception as err:
                print(f"[X] LỖI TRUYỀN NHẬN: {err}\n")
                break

    finally:
        client.close()


if __name__ == "__main__":
    main()
