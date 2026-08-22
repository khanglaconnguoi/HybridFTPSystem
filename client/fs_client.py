import os
import hashlib
from typing import Generator

# Thư mục lưu trữ dữ liệu mặc định của Client
CLIENT_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "client_data"))
os.makedirs(CLIENT_DATA_DIR, exist_ok=True)


class FsClient:
    """
    Thao tác tệp tin cục bộ (Local File System) và tính toán Checksum phía Client (Module C).
    """

    @staticmethod
    def _resolve(filepath: str) -> str:
        """Chuẩn hóa đường dẫn tập tin phía Client vào thư mục client_data."""
        if os.path.isabs(filepath):
            return filepath
        return os.path.join(CLIENT_DATA_DIR, filepath)

    @staticmethod
    def read_file(filepath: str) -> bytes | None:
        """Đọc toàn bộ file local dạng bytes. Trả về None nếu có lỗi."""
        filepath = FsClient._resolve(filepath)
        try:
            with open(filepath, "rb") as f:
                return f.read()
        except OSError:
            return None

    @staticmethod
    def read_file_chunks(filepath: str, chunk_size: int = 8192) -> Generator[bytes, None, None]:
        """
        Generator đọc file local theo từng khối đệm (Chunking).
        Tối ưu hóa bộ nhớ RAM cho các tập tin dung lượng lớn (vài GB).
        """
        filepath = FsClient._resolve(filepath)
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    yield chunk
        except OSError:
            return

    @staticmethod
    def write_file(filepath: str, data: bytes) -> bool:
        """Ghi dữ liệu nhị phân vào file local. Tự động tạo thư mục cha nếu chưa có."""
        filepath = FsClient._resolve(filepath)
        try:
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(data)
            return True
        except OSError:
            return False

    @staticmethod
    def sha256(filepath: str) -> str | None:
        """Tính mã băm SHA-256 của file local theo từng khối 8KB."""
        filepath = FsClient._resolve(filepath)
        h = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()
        except OSError:
            return None

    @staticmethod
    def hash_file(filepath: str) -> str | None:
        """Tính mã băm MD5 của file local theo từng khối 8KB."""
        filepath = FsClient._resolve(filepath)
        h = hashlib.md5()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()
        except OSError:
            return None


class Display:
    """
    Quản lý toàn bộ giao diện hiển thị Terminal phía Client.
    Tách biệt hoàn toàn phần I/O để dễ dàng tích hợp hoặc thay thế bằng GUI sau này.
    """

    @staticmethod
    def progress(transferred: int, total: int, width: int = 40) -> None:
        """Hiển thị thanh tiến trình truyền tải (Progress Bar) theo thời gian thực."""
        ratio = min(1.0, max(0.0, transferred / total)) if total > 0 else 1.0
        filled = int(width * ratio)
        bar = "=" * filled + "-" * (width - filled)
        pct = ratio * 100
        print(
            f"\r  [{bar}] {pct:5.1f}%  {transferred}/{total} B",
            end="",
            flush=True,
        )
        if transferred >= total:
            print()

    @staticmethod
    def list_output(raw: str) -> None:
        """Định dạng danh sách thư mục trả về từ lệnh LIST / NLST với khung viền đẹp mắt."""
        print("\n" + "─" * 64)
        for line in raw.strip().splitlines():
            print("  " + line)
        print("─" * 64 + "\n")

    @staticmethod
    def reply(cmd: str, reply: str) -> None:
        """Hiển thị phản hồi từ Server kèm mã trạng thái và icon trực quan."""
        clean_reply = reply.strip() if reply else ""
        code = clean_reply[:3] if len(clean_reply) >= 3 else "???"
        # Các mã 1xx, 2xx, 3xx là phản hồi thành công/tiếp diễn
        mark = "[OK]" if code[0] in ("1", "2", "3") else "[FAIL]"
        print(f"  {mark} [{code}] {cmd}")
        if clean_reply:
            for line in clean_reply.splitlines():
                print(f"      {line}")

    @staticmethod
    def hash_compare(local_hash: str, server_reply: str) -> bool:
        """Tự động bóc tách chuỗi phản hồi Server và so sánh đối soát mã băm."""
        server_hash = server_reply.split("=")[-1].strip() if "=" in server_reply else server_reply.strip()
        # Loại bỏ các prefix mã trạng thái nếu có
        if " " in server_hash:
            server_hash = server_hash.split()[-1]

        match = (local_hash is not None) and (local_hash.lower() == server_hash.lower())
        status = "MATCH [OK]" if match else "MISMATCH [FAIL]"
        print(f"  Hash: {status}")
        print(f"    Local:  {local_hash}")
        print(f"    Server: {server_hash}")
        return match
