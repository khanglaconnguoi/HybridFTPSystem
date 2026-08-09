from abc import ABC, abstractmethod

class IDataHandler(ABC):
    """
    Interface mà CommandDispatcher dùng để giao tiếp với Module B.
    Module B phải implement tất cả các method này.
    """

    @abstractmethod
    def handle_type(self, session, arg: str) -> None:
        """TYPE A|I — đặt chế độ truyền ASCII hoặc Binary."""

    @abstractmethod
    def handle_mode(self, session, arg: str) -> None:
        """MODE S|B|C — đặt transfer mode."""

    @abstractmethod
    def handle_port(self, session, arg: str) -> None:
        """PORT h1,h2,h3,h4,p1,p2 — Active mode: client báo địa chỉ data."""

    @abstractmethod
    def handle_pasv(self, session, arg: str) -> None:
        """PASV — Passive mode: server mở port UDP, trả địa chỉ cho client."""

    @abstractmethod
    def handle_retr(self, session, filename: str) -> None:
        """RETR filename — gửi file về client qua RDT."""

    @abstractmethod
    def handle_stor(self, session, filename: str) -> None:
        """STOR filename — nhận file từ client qua RDT."""

    @abstractmethod
    def handle_stou(self, session, arg: str) -> None:
        """STOU — nhận file, tự sinh tên duy nhất."""

    @abstractmethod
    def handle_appe(self, session, filename: str) -> None:
        """APPE filename — nhận và nối thêm vào file đã có."""

    @abstractmethod
    def handle_hash(self, session, filename: str) -> None:
        """HASH filename — tính SHA-256, gửi về client."""

    @abstractmethod
    def handle_abor(self, session, arg: str) -> None:
        """ABOR — dừng transfer đang chạy, reset kênh data."""


class IFsHandler(ABC):
    """
    Interface mà CommandDispatcher dùng để giao tiếp với Module C.
    Module C phải implement tất cả các method này.
    """

    @abstractmethod
    def resolve_path(self, session, requested: str) -> str | None:
        """
        Chuẩn hoá và kiểm tra sandbox.
        Trả về đường dẫn tuyệt đối an toàn, hoặc None nếu path traversal.
        """

    @abstractmethod
    def handle_cwd(self, session, path: str) -> None:
        """CWD path — thay đổi thư mục làm việc."""

    @abstractmethod
    def handle_cdup(self, session, arg: str) -> None:
        """CDUP — lên thư mục cha."""

    @abstractmethod
    def handle_mkd(self, session, dirname: str) -> None:
        """MKD dirname — tạo thư mục."""

    @abstractmethod
    def handle_rmd(self, session, dirname: str) -> None:
        """RMD dirname — xoá thư mục rỗng."""

    @abstractmethod
    def handle_list(self, session, path: str) -> None:
        """LIST [path] — liệt kê chi tiết (tên, kích thước, loại, quyền)."""

    @abstractmethod
    def handle_nlst(self, session, path: str) -> None:
        """NLST [path] — liệt kê tên file thuần tuý."""

    @abstractmethod
    def handle_size(self, session, filename: str) -> None:
        """SIZE filename — trả kích thước file tính bằng byte."""

    @abstractmethod
    def handle_mdtm(self, session, filename: str) -> None:
        """MDTM filename — trả timestamp sửa đổi cuối (YYYYMMDDhhmmss)."""

    @abstractmethod
    def handle_dele(self, session, filename: str) -> None:
        """DELE filename — xoá file."""

    @abstractmethod
    def handle_rnfr(self, session, oldname: str) -> None:
        """RNFR oldname — bắt đầu rename, lưu tên cũ vào session."""

    @abstractmethod
    def handle_rnto(self, session, newname: str) -> None:
        """RNTO newname — hoàn thành rename từ RNFR."""
