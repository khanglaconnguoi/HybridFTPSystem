import os
import sys
import stat
import time
import hashlib

# Thêm thư mục gốc vào sys.path để có thể import từ folder 'common'
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from common.reply_codes import ReplyCode

# Tạo đường dẫn tuyệt đối cho kho dữ liệu Sandbox của Server
ROOT_DIR = os.path.join(BASE_DIR, "storage")
os.makedirs(ROOT_DIR, exist_ok=True)


# ----------------------------------------------------------------------
# MODULE C CUSTOM EXCEPTIONS
# ----------------------------------------------------------------------
class FileSystemError(Exception):
    """Ngoại lệ cơ sở cho tất cả lỗi thuộc Module C (File System Management)."""
    def __init__(self, message: str = "File system error", reply_code: ReplyCode = ReplyCode.FILE_UNAVAILABLE):
        super().__init__(message)
        self.reply_code = reply_code


class PathOutOfBoundsError(FileSystemError):
    """Lỗi vi phạm ranh giới thư mục gốc (Sandbox Violation)."""
    def __init__(self, message: str = "Path is outside the allowed root directory"):
        super().__init__(message, reply_code=ReplyCode.FILE_UNAVAILABLE)


class FileNotFoundFSConstraintError(FileSystemError):
    """Lỗi tập tin hoặc thư mục không tồn tại."""
    def __init__(self, message: str = "File or directory not found"):
        super().__init__(message, reply_code=ReplyCode.FILE_UNAVAILABLE)


class FileAlreadyExistsError(FileSystemError):
    """Lỗi tập tin hoặc thư mục đã tồn tại."""
    def __init__(self, message: str = "File or directory already exists"):
        super().__init__(message, reply_code=ReplyCode.FILE_UNAVAILABLE)


class PermissionFSDeniedError(FileSystemError):
    """Lỗi vi phạm quyền truy cập đọc/ghi (Permission Denied)."""
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, reply_code=ReplyCode.FILE_UNAVAILABLE)


class InvalidCommandSequenceError(FileSystemError):
    """Lỗi vi phạm trình tự gọi lệnh (VD: gọi RNTO khi chưa gọi RNFR)."""
    def __init__(self, message: str = "RNFR command required first"):
        super().__init__(message, reply_code=ReplyCode.BAD_SEQUENCE)


# ----------------------------------------------------------------------
# MODULE C CORE CLASS: FSManager
# ----------------------------------------------------------------------
class FSManager:
    """
    Quản lý toàn bộ thao tác tệp tin và thư mục (Module C).
    Đảm bảo quy tắc Sandbox cách ly đường dẫn và tuân thủ các lệnh FTP.
    """

    def __init__(self, session=None, root_dir: str = ROOT_DIR):
        self.session = session
        self.root_dir = os.path.abspath(root_dir)
        self.current_rel_path = "/"
        self.rename_pending = None

    def _resolve_path(self, requested_path: str):
        """
        Phương thức nội bộ: Phân giải đường dẫn và kiểm tra rào chắn Sandbox.
        Đầu vào: requested_path (str)
        Đầu ra: (is_safe: bool, target_abs: str, new_virtual_path: str)
        """
        try:
            if not requested_path:
                requested_path = ""

            if requested_path.startswith("/") or requested_path.startswith("\\"):
                combined = os.path.join(self.root_dir, requested_path.lstrip("/\\"))
            else:
                curr_abs = os.path.join(self.root_dir, self.current_rel_path.lstrip("/\\"))
                combined = os.path.join(curr_abs, requested_path)

            target_abs = os.path.abspath(combined)

            # Kiểm tra Rào chắn Sandbox (Anti Path Traversal)
            is_safe = os.path.commonpath([self.root_dir, target_abs]) == self.root_dir
            if not is_safe:
                return False, target_abs, self.current_rel_path

            rel_path = os.path.relpath(target_abs, self.root_dir)
            if rel_path == ".":
                new_virtual_path = "/"
            else:
                new_virtual_path = "/" + rel_path.replace("\\", "/")

            return True, target_abs, new_virtual_path
        except (ValueError, Exception):
            return False, "", self.current_rel_path

    def resolve_path(self, requested: str) -> str | None:
        """
        Interface công khai cho Module B (RdtEngine) gọi:
        Trả về đường dẫn tuyệt đối an toàn trên đĩa nếu nằm trong Sandbox, ngược lại trả về None.
        """
        is_safe, target_abs, _ = self._resolve_path(requested)
        return target_abs if is_safe else None

    def handle_pwd(self, arg: str = ""):
        """Xử lý lệnh PWD: Trả về đường dẫn ảo hiện tại theo mã FTP 257"""
        msg = f'"{self.current_rel_path}" is the current directory.'
        return True, ReplyCode.PATH_CREATED.format(custom_msg=msg)

    def handle_cwd(self, path: str = ""):
        """Xử lý lệnh CWD: Thay đổi thư mục làm việc hiện tại"""
        is_safe, target_abs, new_virtual_path = self._resolve_path(path)

        if not is_safe:
            return False, ReplyCode.FILE_UNAVAILABLE.format()

        if not os.path.exists(target_abs) or not os.path.isdir(target_abs):
            return False, ReplyCode.FILE_UNAVAILABLE.format()

        self.current_rel_path = new_virtual_path
        return True, ReplyCode.FILE_ACTION_OK.format()

    def handle_cdup(self, arg: str = ""):
        """Xử lý lệnh CDUP: Chuyển lên thư mục cha"""
        return self.handle_cwd("..")

    def handle_mkd(self, dirname: str = ""):
        """Xử lý lệnh MKD: Tạo thư mục mới"""
        is_safe, target_abs, _ = self._resolve_path(dirname)
        if not is_safe or os.path.exists(target_abs):
            return False, ReplyCode.FILE_UNAVAILABLE.format()

        try:
            os.mkdir(target_abs)
            msg = f'"{dirname}" directory created.'
            return True, ReplyCode.PATH_CREATED.format(custom_msg=msg)
        except Exception:
            return False, ReplyCode.FILE_UNAVAILABLE.format()

    def handle_rmd(self, dirname: str = ""):
        """Xử lý lệnh RMD: Xóa thư mục rỗng"""
        is_safe, target_abs, _ = self._resolve_path(dirname)
        if not is_safe or not os.path.exists(target_abs) or not os.path.isdir(target_abs):
            return False, ReplyCode.FILE_UNAVAILABLE.format()

        try:
            os.rmdir(target_abs)
            return True, ReplyCode.FILE_ACTION_OK.format()
        except Exception:
            return False, ReplyCode.FILE_UNAVAILABLE.format()

    def handle_nlst(self, path: str = ""):
        """Xử lý lệnh NLST: Trả về danh sách tên tệp/thư mục"""
        is_safe, target_abs, _ = self._resolve_path(path)
        if not is_safe or not os.path.exists(target_abs) or not os.path.isdir(target_abs):
            return False, ReplyCode.FILE_UNAVAILABLE.format()

        if not os.access(target_abs, os.R_OK):
            return False, ReplyCode.FILE_UNAVAILABLE.format()

        try:
            names = os.listdir(target_abs)
            data_str = "\r\n".join(names) + "\r\n" if names else ""
            return True, data_str
        except Exception:
            return False, ReplyCode.FILE_UNAVAILABLE.format()

    def handle_list(self, path: str = ""):
        """Xử lý lệnh LIST: Trả về danh sách chi tiết (name, size, type, permissions)"""
        is_safe, target_abs, _ = self._resolve_path(path)
        if not is_safe or not os.path.exists(target_abs) or not os.path.isdir(target_abs):
            return False, ReplyCode.FILE_UNAVAILABLE.format()

        if not os.access(target_abs, os.R_OK):
            return False, ReplyCode.FILE_UNAVAILABLE.format()

        try:
            names = os.listdir(target_abs)
            if not names:
                return True, ""

            data_str = ""
            for name in names:
                item_path = os.path.join(target_abs, name)
                info = os.stat(item_path)
                perm_str = stat.filemode(info.st_mode)
                file_size = info.st_size
                line = f"{perm_str} {file_size:>10} {name}\r\n"
                data_str += line

            return True, data_str
        except Exception:
            return False, ReplyCode.FILE_UNAVAILABLE.format()

    def handle_size(self, path: str = ""):
        """Xử lý lệnh SIZE: Trả về độ lớn của tập tin (dùng mã 213 FILE_STATUS)"""
        is_safe, target_abs, _ = self._resolve_path(path)
        if not is_safe or not os.path.exists(target_abs) or not os.path.isfile(target_abs):
            return False, ReplyCode.FILE_UNAVAILABLE.format()

        if not os.access(target_abs, os.R_OK):
            return False, ReplyCode.FILE_UNAVAILABLE.format()

        try:
            size = os.stat(target_abs).st_size
            return True, ReplyCode.FILE_STATUS.format(custom_msg=str(size))
        except Exception:
            return False, ReplyCode.FILE_UNAVAILABLE.format()

    def handle_mdtm(self, path: str = ""):
        """Xử lý lệnh MDTM: Trả về mốc thời gian sửa đổi UTC YYYYMMDDHHMMSS (dùng mã 213 FILE_STATUS)"""
        is_safe, target_abs, _ = self._resolve_path(path)
        if not is_safe or not os.path.exists(target_abs) or not os.path.isfile(target_abs):
            return False, ReplyCode.FILE_UNAVAILABLE.format()

        if not os.access(target_abs, os.R_OK):
            return False, ReplyCode.FILE_UNAVAILABLE.format()

        try:
            mtime = os.path.getmtime(target_abs)
            mtime_str = time.strftime("%Y%m%d%H%M%S", time.gmtime(mtime))
            return True, ReplyCode.FILE_STATUS.format(custom_msg=mtime_str)
        except Exception:
            return False, ReplyCode.FILE_UNAVAILABLE.format()

    def handle_dele(self, path: str = ""):
        """Xử lý lệnh DELE: Xóa tập tin"""
        is_safe, target_abs, _ = self._resolve_path(path)
        if not is_safe or not os.path.exists(target_abs) or not os.path.isfile(target_abs):
            return False, ReplyCode.FILE_UNAVAILABLE.format()

        if not os.access(target_abs, os.W_OK):
            return False, ReplyCode.FILE_UNAVAILABLE.format()

        try:
            os.remove(target_abs)
            return True, ReplyCode.FILE_ACTION_OK.format()
        except Exception:
            return False, ReplyCode.FILE_UNAVAILABLE.format()

    def handle_stou(self, path: str = "file.tmp"):
        """Xử lý lệnh STOU: Tạo file độc nhất 0-byte giữ chỗ"""
        is_safe, target_abs, _ = self._resolve_path(path)
        if not is_safe:
            return False, ReplyCode.FILE_UNAVAILABLE.format()

        base_dir = os.path.dirname(target_abs)
        filename = os.path.basename(target_abs)
        name, ext = os.path.splitext(filename)
        if not name:
            name, ext = "file", ".tmp"

        unique_abs = target_abs
        counter = 1
        while os.path.exists(unique_abs):
            unique_name = f"{name}_{counter}{ext}"
            unique_abs = os.path.join(base_dir, unique_name)
            counter += 1

        try:
            with open(unique_abs, "xb") as f:
                pass
            return True, ReplyCode.FILE_ACTION_OK.format()
        except Exception:
            return False, ReplyCode.FILE_UNAVAILABLE.format()

    def handle_appe(self, path: str = ""):
        """Xử lý lệnh APPE: Chuẩn bị nối dữ liệu vào file"""
        is_safe, target_abs, _ = self._resolve_path(path)
        if not is_safe:
            return False, ReplyCode.FILE_UNAVAILABLE.format()

        if os.path.exists(target_abs):
            if not os.path.isfile(target_abs) or not os.access(target_abs, os.W_OK):
                return False, ReplyCode.FILE_UNAVAILABLE.format()
        else:
            parent_dir = os.path.dirname(target_abs)
            if not os.path.exists(parent_dir) or not os.access(parent_dir, os.W_OK):
                return False, ReplyCode.FILE_UNAVAILABLE.format()

        return True, ReplyCode.OPENING_DATA_CONN.format(), target_abs

    def handle_rnfr(self, oldname: str = ""):
        """Xử lý bước 1 của đổi tên (RNFR): Kiểm tra file tồn tại và lưu vết"""
        is_safe, target_abs, _ = self._resolve_path(oldname)
        if not is_safe or not os.path.exists(target_abs):
            return False, ReplyCode.FILE_UNAVAILABLE.format()

        self.rename_pending = target_abs
        return True, ReplyCode.PENDING_RNTO.format(), target_abs

    def handle_rnto(self, newname: str = ""):
        """Xử lý bước 2 của đổi tên (RNTO): Thực hiện đổi tên thực tế trên đĩa"""
        try:
            if not self.rename_pending or not os.path.exists(self.rename_pending):
                return False, ReplyCode.BAD_SEQUENCE.format()

            if not newname:
                return False, ReplyCode.FILE_UNAVAILABLE.format()

            is_safe, new_abs, _ = self._resolve_path(newname)
            if not is_safe or os.path.exists(new_abs):
                return False, ReplyCode.FILE_UNAVAILABLE.format()

            os.rename(self.rename_pending, new_abs)
            self.rename_pending = None
            return True, ReplyCode.FILE_ACTION_OK.format()
        except Exception:
            return False, ReplyCode.FILE_UNAVAILABLE.format()

    def handle_hash(self, path: str = "", algo: str = "sha256"):
        """Xử lý lệnh HASH: Tính mã băm SHA256 hoặc MD5 (dùng mã 213 FILE_STATUS)"""
        is_safe, target_abs, _ = self._resolve_path(path)
        if not is_safe or not os.path.isfile(target_abs):
            return False, ReplyCode.FILE_UNAVAILABLE.format()

        if algo.lower() == "md5":
            hasher = hashlib.md5()
        else:
            hasher = hashlib.sha256()

        try:
            with open(target_abs, "rb") as f:
                while chunk := f.read(1024):
                    hasher.update(chunk)
            hash_hex = hasher.hexdigest()
            return True, ReplyCode.FILE_STATUS.format(custom_msg=hash_hex)
        except Exception:
            return False, ReplyCode.FILE_UNAVAILABLE.format()


