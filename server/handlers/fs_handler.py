import os
import sys
import stat
import time
import hashlib
from contextlib import contextmanager


# Thêm thư mục gốc vào sys.path để có thể import từ folder 'common'
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from common.reply_codes import ReplyCode
from common.constants import CHUNK_SIZE
from server.fs.path_guard import PathGuard
from server.fs.dir_walker import DirWalker

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
# MODULE C CORE CLASS: FSManager / FsHandler
# ----------------------------------------------------------------------
class FSManager:
    """
    Quản lý toàn bộ thao tác tệp tin và thư mục (Module C).
    Đảm bảo quy tắc Sandbox cách ly đường dẫn và tuân thủ các lệnh FTP.
    """

    def __init__(self, session=None, root_dir: str = ROOT_DIR):
        self.session = session
        self._guard = PathGuard(root_dir)
        self._walker = DirWalker()
        self.current_rel_path = "/"
        self.rename_pending = None

    @property
    def root_dir(self) -> str:
        return self._guard.root

    def _resolve_path(self, requested_path: str):
        """
        Phương thức nội bộ: Ủy quyền cho PathGuard kiểm tra rào chắn Sandbox.
        Đầu vào: requested_path (str)
        Đầu ra: (is_safe: bool, target_abs: str, new_virtual_path: str)
        """
        return self._guard.safe_join(self.current_rel_path, requested_path)

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
        """Xử lý lệnh NLST: Trả về danh sách tên tệp/thư mục qua DirWalker"""
        is_safe, target_abs, _ = self._resolve_path(path)
        if not is_safe or not os.path.exists(target_abs) or not os.path.isdir(target_abs):
            return False, ReplyCode.FILE_UNAVAILABLE.format()

        if not os.access(target_abs, os.R_OK):
            return False, ReplyCode.FILE_UNAVAILABLE.format()

        try:
            names_str = self._walker.list_names(target_abs)
            data_str = names_str + "\r\n" if names_str else ""
            return True, data_str
        except Exception:
            return False, ReplyCode.FILE_UNAVAILABLE.format()

    def handle_list(self, path: str = ""):
        """Xử lý lệnh LIST: Trả về danh sách chi tiết chuẩn Unix ls -l qua DirWalker"""
        is_safe, target_abs, _ = self._resolve_path(path)
        if not is_safe or not os.path.exists(target_abs) or not os.path.isdir(target_abs):
            return False, ReplyCode.FILE_UNAVAILABLE.format()

        if not os.access(target_abs, os.R_OK):
            return False, ReplyCode.FILE_UNAVAILABLE.format()

        try:
            listing = self._walker.list_detailed(target_abs)
            data_str = listing + "\r\n" if listing else ""
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

    def handle_stou(self, path: str = ""):
        """
        Xử lý lệnh STOU (Store Unique): Tạo file độc nhất 0-byte giữ chỗ.
        - Tự động sinh tên động bằng mốc thời gian Timestamp (stou_YYYYMMDD_HHMMSS.tmp) nếu rỗng.
        - Trả về đường dẫn ảo độc nhất đã được khởi tạo trong chuỗi phản hồi 250 chuẩn RFC 959.
        """
        if not path or not path.strip():
            ts = time.strftime("%Y%m%d_%H%M%S")
            path = f"stou_{ts}.tmp"

        is_safe, target_abs, virtual_path = self._resolve_path(path)
        if not is_safe:
            return False, ReplyCode.FILE_UNAVAILABLE.format()

        base_dir = os.path.dirname(target_abs)
        filename = os.path.basename(target_abs)
        name, ext = os.path.splitext(filename)
        if not name:
            ts = time.strftime("%Y%m%d_%H%M%S")
            name = f"stou_{ts}"
            if not ext:
                ext = ".tmp"

        unique_abs = target_abs
        unique_virtual = virtual_path
        counter = 1
        while os.path.exists(unique_abs):
            unique_name = f"{name}_{counter}{ext}"
            unique_abs = os.path.join(base_dir, unique_name)
            unique_virtual = self._guard.relative_display(unique_abs)
            counter += 1

        try:
            with open(unique_abs, "xb") as f:
                pass
            msg = f"FILE: {unique_virtual}"
            return True, ReplyCode.FILE_ACTION_OK.format(custom_msg=msg)
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
                while chunk := f.read(CHUNK_SIZE):
                    hasher.update(chunk)
            hash_hex = hasher.hexdigest()
            return True, ReplyCode.FILE_STATUS.format(custom_msg=hash_hex)
        except Exception:
            return False, ReplyCode.FILE_UNAVAILABLE.format()

    @contextmanager
    def safe_write_stream(self, path: str = "", mode: str = "wb"):
        """
        Quản lý luồng ghi file an toàn trong Sandbox với tính năng Tự động Rollback (Hồi tác).
        - Đảm bảo kiểm tra ranh giới thư mục gốc (Sandbox).
        - Lưu vết độ dài tệp ban đầu (original_size).
        - Nếu có lỗi/ngắt kết nối trong quá trình ghi: Tự động khôi phục tệp về độ dài ban đầu bằng truncate().
        """
        is_safe, target_abs, _ = self._resolve_path(path)
        if not is_safe:
            raise PathOutOfBoundsError(f"Đường dẫn vi phạm Sandbox: {path}")

        if os.path.exists(target_abs):
            if not os.path.isfile(target_abs) or not os.access(target_abs, os.W_OK):
                raise PermissionFSDeniedError(f"Không có quyền ghi vào tập tin: {path}")
            original_size = os.path.getsize(target_abs)
        else:
            parent_dir = os.path.dirname(target_abs)
            if not os.path.exists(parent_dir) or not os.access(parent_dir, os.W_OK):
                raise PermissionFSDeniedError(f"Không có quyền ghi vào thư mục: {parent_dir}")
            original_size = 0

        f = open(target_abs, mode)
        try:
            yield f.write
        except Exception as err:
            f.close()
            if os.path.exists(target_abs):
                if original_size == 0 and mode in ("wb", "xb"):
                    try:
                        os.remove(target_abs)
                    except OSError:
                        pass
                else:
                    try:
                        with open(target_abs, "a+b") as rollback_f:
                            rollback_f.truncate(original_size)
                    except OSError:
                        pass
            raise err
        else:
            f.close()


# Bí danh FsHandler để linh hoạt cách gọi
FsHandler = FSManager
