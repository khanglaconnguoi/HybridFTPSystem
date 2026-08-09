import socket
import hashlib
import os
from common.interfaces import IDataHandler
from common.reply_codes import ReplyCode
from common.rdt.sender   import RdtSender
from common.rdt.receiver import RdtReceiver
from server.session import ClientSession

class DataHandler(IDataHandler):
    """
    Xử lý tất cả lệnh liên quan đến kênh dữ liệu UDP.
    Mỗi session có 1 DataHandler riêng — không chia sẻ state giữa sessions.
    """

    def __init__(self, session: ClientSession):
        self._session = session
        self._data_sock: socket.socket | None = None

    # ── Thiết lập kênh data ────────────────────────────────────

    def handle_type(self, session: ClientSession, arg: str) -> None:
        t = arg.strip().upper()
        if t not in ("A", "I"):
            session.send_reply(ReplyCode.SYNTAX_ERROR_PARAM.format(
                "Type must be A or I."
            ))
            return
        session.data_config.transfer_type = t
        session.send_reply(ReplyCode.CMD_OK.format(f"Type set to {t}."))

    def handle_mode(self, session: ClientSession, arg: str) -> None:
        m = arg.strip().upper()
        if m not in ("S", "B", "C"):
            session.send_reply(ReplyCode.SYNTAX_ERROR_PARAM.format())
            return
        session.data_config.transfer_mode = m
        session.send_reply(ReplyCode.CMD_OK.format(f"Mode set to {m}."))

    def handle_port(self, session: ClientSession, arg: str) -> None:
        """Active mode: client gửi địa chỉ UDP của mình."""
        try:
            parts = arg.strip().split(",")
            ip   = ".".join(parts[:4])
            port = (int(parts[4]) << 8) + int(parts[5])
            session.data_config.mode = "PORT"
            session.data_config.client_data_addr = (ip, port)
            session.send_reply(ReplyCode.CMD_OK.format("PORT command successful."))
        except (ValueError, IndexError):
            session.send_reply(ReplyCode.SYNTAX_ERROR_PARAM.format())

    def handle_pasv(self, session: ClientSession, _arg: str) -> None:
        """Passive mode: mở cổng UDP ngẫu nhiên, báo client."""
        if self._data_sock:
            self._data_sock.close()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("", 0))
        _, port = sock.getsockname()
        self._data_sock = sock
        session.data_config.mode = "PASV"
        session.data_config.server_data_port = port

        local_ip = session.conn.getsockname()[0].replace(".", ",")
        p1, p2 = port >> 8, port & 0xFF
        session.send_reply(
            f"227 Entering Passive Mode ({local_ip},{p1},{p2}).\r\n"
        )

    # ── Transfer ───────────────────────────────────────────────

    def _get_data_socket(self, session: ClientSession) -> socket.socket | None:
        """Trả về UDP socket đã cấu hình theo mode PASV/PORT."""
        cfg = session.data_config
        if cfg.mode == "PASV":
            if self._data_sock is None:
                session.send_reply(ReplyCode.CANT_OPEN_DATA.format(
                    "No data channel configured. Send PASV or PORT first."
                ))
            return self._data_sock  # socket đã bind sẵn
        elif cfg.mode == "PORT" and cfg.client_data_addr:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("", 0))
            return sock
        session.send_reply(ReplyCode.CANT_OPEN_DATA.format(
            "No data channel configured. Send PASV or PORT first."
        ))
        return None

    def handle_retr(self, session: ClientSession, filename: str) -> None:
        """Gửi file về client qua RDT."""
        from server.handlers.fs_handler import FsHandler  # import lazy tránh circular
        safe_path = FsHandler(session).resolve_path(session, filename)
        if not safe_path or not os.path.isfile(safe_path):
            session.send_reply(ReplyCode.FILE_UNAVAIL.format())
            return

        sock = self._get_data_socket(session)
        if not sock:
            return

        try:
            session.send_reply(ReplyCode.FILE_STATUS_OK.format(
                f"Opening data connection for {filename}."
            ))
            with open(safe_path, "rb") as f:
                data = f.read()

            peer = session.data_config.client_data_addr
            sender = RdtSender(sock, peer)
            ok = sender.send_bytes(data)
            if ok:
                session.send_reply(ReplyCode.DATA_CONN_CLOSE.format())
            else:
                session.send_reply(ReplyCode.CONN_CLOSED_ABORT.format())
        except OSError as e:
            session.send_reply(ReplyCode.FILE_UNAVAIL.format(str(e)))
        finally:
            if session.data_config.mode == "PORT":
                sock.close()

    def handle_stor(self, session: ClientSession, filename: str) -> None:
        """Nhận file từ client qua RDT."""
        from server.handlers.fs_handler import FsHandler
        safe_path = FsHandler(session).resolve_path(session, filename)
        if not safe_path:
            session.send_reply(ReplyCode.FILE_UNAVAIL.format("Access denied."))
            return

        sock = self._get_data_socket(session)
        if not sock:
            return

        try:
            session.send_reply(ReplyCode.FILE_STATUS_OK.format(
                f"Ready to receive {filename}."
            ))
            receiver = RdtReceiver(sock)
            peer = session.data_config.client_data_addr
            data = receiver.receive_bytes(peer)
            if data is None:
                session.send_reply(ReplyCode.CONN_CLOSED_ABORT.format())
                return
            with open(safe_path, "wb") as f:
                f.write(data)
            session.send_reply(ReplyCode.DATA_CONN_CLOSE.format())
        except OSError as e:
            session.send_reply(ReplyCode.FILE_UNAVAIL.format(str(e)))
        finally:
            if session.data_config.mode == "PORT":
                sock.close()

    def handle_stou(self, session: ClientSession, _arg: str) -> None:
        """Nhận file với tên duy nhất được server sinh ra."""
        import uuid
        unique_name = f"upload_{uuid.uuid4().hex[:8]}.bin"
        self.handle_stor(session, unique_name)

    def handle_appe(self, session: ClientSession, filename: str) -> None:
        """Nhận và nối thêm vào file đã có."""
        from server.handlers.fs_handler import FsHandler
        safe_path = FsHandler(session).resolve_path(session, filename)
        if not safe_path:
            session.send_reply(ReplyCode.FILE_UNAVAIL.format("Access denied."))
            return

        sock = self._get_data_socket(session)
        if not sock:
            return

        try:
            session.send_reply(ReplyCode.FILE_STATUS_OK.format(
                f"Appending to {filename}."
            ))
            receiver = RdtReceiver(sock)
            data = receiver.receive_bytes(session.data_config.client_data_addr)
            if data is None:
                session.send_reply(ReplyCode.CONN_CLOSED_ABORT.format())
                return
            with open(safe_path, "ab") as f:
                f.write(data)
            session.send_reply(ReplyCode.DATA_CONN_CLOSE.format())
        except OSError as e:
            session.send_reply(ReplyCode.FILE_UNAVAIL.format(str(e)))

    def handle_hash(self, session: ClientSession, filename: str) -> None:
        """Tính SHA-256 của file và gửi về client."""
        from server.handlers.fs_handler import FsHandler
        safe_path = FsHandler(session).resolve_path(session, filename)
        if not safe_path or not os.path.isfile(safe_path):
            session.send_reply(ReplyCode.FILE_UNAVAIL.format())
            return
        h = hashlib.sha256()
        with open(safe_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        digest = h.hexdigest()
        session.send_reply(ReplyCode.CMD_OK.format(
            f"SHA-256 {filename} = {digest}"
        ))

    def handle_abor(self, session: ClientSession, _arg: str) -> None:
        """Dừng transfer đang chạy, đóng kênh data."""
        session.transfer_active = False
        if self._data_sock:
            try:
                self._data_sock.close()
            except OSError:
                pass
            self._data_sock = None
        session.send_reply(ReplyCode.DATA_CONN_CLOSE.format("ABOR acknowledged."))
