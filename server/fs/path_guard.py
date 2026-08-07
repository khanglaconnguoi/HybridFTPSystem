import os


class PathGuard:
    """
    Quản lý rào chắn Sandbox và chuyển đổi đường dẫn an toàn cho FTP Server.
    Cơ chế bảo vệ Anti Path Traversal: Đảm bảo mọi thao tác đĩa không vượt quá root_dir.
    """

    def __init__(self, sandbox_root: str):
        self._root = os.path.abspath(os.path.realpath(sandbox_root))
        os.makedirs(self._root, exist_ok=True)

    @property
    def root(self) -> str:
        """Đường dẫn tuyệt đối chuẩn hóa của thư mục Sandbox gốc."""
        return self._root

    def safe_join(self, current_virtual_dir: str, requested_path: str) -> tuple[bool, str, str]:
        """
        Phân giải đường dẫn và kiểm tra rào chắn Sandbox.
        Đầu vào:
            current_virtual_dir (str): Thư mục ảo hiện tại (VD: "/", "/sub")
            requested_path (str): Đường dẫn người dùng yêu cầu (tương đối hoặc tuyệt đối)
        Đầu ra:
            (is_safe: bool, target_abs: str, new_virtual_path: str)
        """
        try:
            if not requested_path:
                requested_path = ""

            if requested_path.startswith("/") or requested_path.startswith("\\"):
                combined = os.path.join(self._root, requested_path.lstrip("/\\"))
            else:
                curr_abs = os.path.join(self._root, current_virtual_dir.lstrip("/\\"))
                combined = os.path.join(curr_abs, requested_path)

            target_abs = os.path.abspath(os.path.realpath(combined))

            # Kiểm tra Rào chắn Sandbox (Anti Path Traversal) bằng os.path.commonpath
            is_safe = os.path.commonpath([self._root, target_abs]) == self._root
            if not is_safe:
                return False, target_abs, current_virtual_dir

            new_virtual_path = self.relative_display(target_abs)
            return True, target_abs, new_virtual_path
        except Exception:
            return False, "", current_virtual_dir

    def relative_display(self, absolute_path: str) -> str:
        """
        Chuyển đổi đường dẫn tuyệt đối trên đĩa thành đường dẫn ảo FTP (/sub/folder).
        """
        try:
            rel_path = os.path.relpath(absolute_path, self._root)
            if rel_path == ".":
                return "/"
            return "/" + rel_path.replace("\\", "/")
        except Exception:
            return "/"
