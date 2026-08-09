import socket
import hashlib
import os
# from common.interfaces import IDataHandler
from common.reply_codes import ReplyCode
from common.rdt.sender   import RdtSender
from common.rdt.receiver import RdtReceiver
from common.constants import CHUNK_SIZE
from server.session import ClientSession

class DataHandler:
    """
    Xử lý tất cả lệnh liên quan đến kênh dữ liệu UDP.
    Mỗi session có 1 DataHandler riêng — không chia sẻ state giữa sessions.
    """

    def __init__(self, session: ClientSession):
        self._session = session
        self._data_sock: socket.socket | None = None

    # ── Thiết lập kênh data ────────────────────────────────────

    def handle_type(self, arg: str) -> None:
        t = arg.strip().upper()
        if t not in ("A", "I"):
            self._session.send_reply(ReplyCode.SYNTAX_ERROR_PARAM.format(
                "Type must be A or I."
            ))
            return
        self._session.data_config.transfer_type = t
        self._session.send_reply(ReplyCode.COMMAND_OK.format(f"Type set to {t}."))

    def handle_mode(self, arg: str) -> None:
        m = arg.strip().upper()
        if m not in ("S", "B", "C"):
            self._session.send_reply(ReplyCode.SYNTAX_ERROR_PARAM.format())
            return
        self._session.data_config.transfer_mode = m
        self._session.send_reply(ReplyCode.COMMAND_OK.format(f"Mode set to {m}."))

    def handle_port(self, arg: str) -> None:
        """Active mode: client gửi địa chỉ UDP của mình."""
        try:
            parts = arg.strip().split(",")
            ip   = ".".join(parts[:4])
            port = (int(parts[4]) << 8) + int(parts[5])
            self._session.data_config.mode = "PORT"
            self._session.data_config.client_data_addr = (ip, port)
            self._session.send_reply(ReplyCode.COMMAND_OK.format("PORT command successful."))
        except (ValueError, IndexError):
            self._session.send_reply(ReplyCode.SYNTAX_ERROR_PARAM.format())

    def handle_pasv(self, _arg: str) -> None:
        """Passive mode: mở cổng UDP ngẫu nhiên, báo client."""
        if self._data_sock:
            self._data_sock.close()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("", 0))
        _, port = sock.getsockname()
        self._data_sock = sock
        self._session.data_config.mode = "PASV"
        self._session.data_config.server_data_port = port

        local_ip = self._session.conn.getsockname()[0].replace(".", ",")
        p1, p2 = port >> 8, port & 0xFF
        self._session.send_reply(
            f"227 Entering Passive Mode ({local_ip},{p1},{p2}).\r\n"
        )

    # ── Transfer ───────────────────────────────────────────────

    def _get_data_socket(self) -> socket.socket | None:
        """Trả về UDP socket đã cấu hình theo mode PASV/PORT."""
        cfg = self._session.data_config
        if cfg.mode == "PASV":
            if self._data_sock is None:
                self._session.send_reply(ReplyCode.CANT_OPEN_DATA_CONN.format(
                    "No data channel configured. Send PASV or PORT first."
                ))
                return None
            return self._data_sock  # socket đã bind sẵn
        elif cfg.mode == "PORT" and cfg.client_data_addr:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("", 0))
            self._data_sock = sock
            return sock
        self._session.send_reply(ReplyCode.CANT_OPEN_DATA_CONN.format(
            "No data channel configured. Send PASV or PORT first."
        ))
        return None

    def handle_retr(self, filename: str) -> None:
        """Gửi file về client qua RDT."""
        from server.handlers.fs_handler import FsHandler  # import lazy tránh circular
        safe_path = FsHandler(self._session).resolve_path(self._session, filename)
        if not safe_path or not os.path.isfile(safe_path):
            self._session.send_reply(ReplyCode.FILE_UNAVAILABLE.format())
            return

        sock = self._get_data_socket()
        if not sock:
            return

        try:
            self._session.send_reply(ReplyCode.OPENING_DATA_CONN.format(
                f"Opening data connection for {filename}."
            ))
            with open(safe_path, "rb") as f:
                data = f.read()

            peer = self._session.data_config.client_data_addr
            sender = RdtSender(sock, peer)
            ok = sender.send_bytes(data)
            if ok:
                self._session.send_reply(ReplyCode.TRANSFER_COMPLETE.format())
            else:
                self._session.send_reply(ReplyCode.TRANSFER_ABORTED.format())
        except OSError as e:
            self._session.send_reply(ReplyCode.FILE_UNAVAILABLE.format(str(e)))
        finally:
            if self._session.data_config.mode == "PORT":
                sock.close()

    def handle_stor(self, filename: str) -> None:
        """Nhận file từ client qua RDT."""
        from server.handlers.fs_handler import FsHandler
        safe_path = FsHandler(self._session).resolve_path(self._session, filename)
        if not safe_path:
            self._session.send_reply(ReplyCode.FILE_UNAVAILABLE.format("Access denied."))
            return

        sock = self._get_data_socket()
        if not sock:
            return

        try:
            self._session.send_reply(ReplyCode.OPENING_DATA_CONN.format(
                f"Ready to receive {filename}."
            ))
            receiver = RdtReceiver(sock)
            peer = self._session.data_config.client_data_addr
            data = receiver.receive_bytes(peer)
            if data is None:
                self._session.send_reply(ReplyCode.TRANSFER_ABORTED.format())
                return
            with open(safe_path, "wb") as f:
                f.write(data)
            self._session.send_reply(ReplyCode.TRANSFER_COMPLETE.format())
        except OSError as e:
            self._session.send_reply(ReplyCode.FILE_UNAVAILABLE.format(str(e)))
        finally:
            if self._session.data_config.mode == "PORT":
                sock.close()

    def handle_stou(self, arg: str) -> None:
        """Nhận file với tên duy nhất được server sinh ra."""
        from server.handlers.fs_handler import FsHandler
        ok, reply = FsHandler(self._session).handle_stou(arg)
        if not ok:
            self._session.send_reply(reply)
            return
        
        self._session.send_reply(reply)
        prefix = "FILE: "
        if prefix in reply:
            virtual_path = reply.split(prefix)[1].strip()
            self.handle_stor(virtual_path)

    def handle_appe(self, filename: str) -> None:
        """Nhận và nối thêm vào file đã có."""
        from server.handlers.fs_handler import FsHandler
        safe_path = FsHandler(self._session).resolve_path(self._session, filename)
        if not safe_path:
            self._session.send_reply(ReplyCode.FILE_UNAVAILABLE.format("Access denied."))
            return

        sock = self._get_data_socket()
        if not sock:
            return

        try:
            self._session.send_reply(ReplyCode.OPENING_DATA_CONN.format(
                f"Appending to {filename}."
            ))
            receiver = RdtReceiver(sock)
            data = receiver.receive_bytes(self._session.data_config.client_data_addr)
            if data is None:
                self._session.send_reply(ReplyCode.TRANSFER_ABORTED.format())
                return
            with open(safe_path, "ab") as f:
                f.write(data)
            self._session.send_reply(ReplyCode.TRANSFER_COMPLETE.format())
        except OSError as e:
            self._session.send_reply(ReplyCode.FILE_UNAVAILABLE.format(str(e)))
        finally:
            if self._session.data_config.mode == "PORT":
                sock.close()

    def handle_hash(self, path: str = "", algo: str = "sha256"):
        """Xử lý lệnh HASH: Tính mã băm SHA256 hoặc MD5 (dùng mã 213 FILE_STATUS)"""
        from server.handlers.fs_handler import FsHandler
        target_abs = FsHandler(self._session).resolve_path(self._session, path)
        if not target_abs or not os.path.isfile(target_abs):
            self._session.send_reply(ReplyCode.FILE_UNAVAILABLE.format())
            return False 

        if algo.lower() == "md5":
            hasher = hashlib.md5()
        else:
            hasher = hashlib.sha256()

        try:
            with open(target_abs, "rb") as f:
                while chunk := f.read(CHUNK_SIZE):
                    hasher.update(chunk)
            hash_hex = hasher.hexdigest()
            self._session.send_reply(ReplyCode.FILE_STATUS.format(custom_msg=hash_hex))
            return True
        except Exception:
            self._session.send_reply(ReplyCode.FILE_UNAVAILABLE.format())
            return False

    def handle_abor(self, _arg: str) -> None:
        """Dừng transfer đang chạy, đóng kênh data."""
        self._session.transfer_active = False
        if self._data_sock:
            try:
                self._data_sock.close()
            except OSError:
                pass
            self._data_sock = None
        self._session.send_reply(ReplyCode.TRANSFER_COMPLETE.format("ABOR acknowledged."))
