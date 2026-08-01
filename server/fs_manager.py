import os
import sys

# Thêm thư mục gốc vào sys.path để có thể import từ folder 'common'
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from common.reply_codes import R_250, R_257, R_550

# Tạo đường dẫn tuyệt đối cho kho dữ liệu Sandbox của Server
ROOT_DIR = os.path.join(BASE_DIR, "storage")

# Tự động tạo thư mục storage trên đĩa cứng nếu chưa có
os.makedirs(ROOT_DIR, exist_ok=True)


class FSManager:
    def __init__(self, root_dir=ROOT_DIR):
        self.root_dir = os.path.abspath(root_dir)
        self.current_rel_path = "/"

    def _resolve_path(self, requested_path):
        """
        Đầu vào: requested_path (Chuỗi do Client gửi lên, ví dụ: 'photos' hoặc '../etc')
        Đầu ra: (is_safe, target_abs, new_virtual_path)
        """
        # BƯỚC 1: Xử lý điểm bắt đầu (Tuyệt đối hay Tương đối?)
        if requested_path.startswith("/") or requested_path.startswith("\\"):
            combined = os.path.join(self.root_dir, requested_path.lstrip("/\\"))
        else:
            curr_abs = os.path.join(self.root_dir, self.current_rel_path.lstrip("/\\"))
            combined = os.path.join(curr_abs, requested_path)

        # BƯỚC 2: Phân giải thành Đường dẫn Tuyệt đối Thật trên đĩa
        target_abs = os.path.abspath(combined)

        # BƯỚC 3: Kiểm tra Rào chắn Sandbox (Anti Path Traversal)
        is_safe = os.path.commonpath([self.root_dir, target_abs]) == self.root_dir

        # BƯỚC 4: Tính lại Đường dẫn Ảo mới cho Client
        rel_path = os.path.relpath(target_abs, self.root_dir)
        
        if rel_path == ".":
            new_virtual_path = "/"
        else:
            new_virtual_path = "/" + rel_path.replace("\\", "/")

        return is_safe, target_abs, new_virtual_path

    def get_pwd(self):
        """Xử lý lệnh PWD: Trả về đường dẫn ảo hiện tại theo mã FTP 257"""
        return True, R_257.format(path=self.current_rel_path)

    def set_cwd(self, target_dir):
        """Xử lý lệnh CWD: Thay đổi thư mục làm việc hiện tại"""
        # 1. Cho đường dẫn đi qua bộ lọc Sandbox
        is_safe, target_abs, new_virtual_path = self._resolve_path(target_dir)

        # 2. Kiểm tra vi phạm Sandbox
        if not is_safe:
            return False, R_550

        # 3. Kiểm tra sự tồn tại
        if not os.path.exists(target_abs):
            return False, R_550

        # 4. Kiểm tra có phải là thư mục hay không
        if not os.path.isdir(target_abs):
            return False, R_550

        # 5. Cập nhật vị trí mới nhất
        self.current_rel_path = new_virtual_path

        # 6. Trả về kết quả THÀNH CÔNG (Mã 250)
        return True, R_250

    def set_cdup(self):
        """Xử lý lệnh CDUP: Chuyển lên thư mục cha"""
        return self.set_cwd("..")

    def make_dir(self, dir_name):
        """Xử lý lệnh MKD: Tạo thư mục mới"""
        # 1. Cho đường dẫn đi qua bộ lọc Sandbox
        is_safe, target_abs, _ = self._resolve_path(dir_name)
        
        # 2. Kiểm tra vi phạm Sandbox
        if not is_safe:
            return False, R_550
        
        # 3. Kiểm tra sự tồn tại (chống ghi đè/trùng lặp)
        if os.path.exists(target_abs):
            return False, R_550

        # 4. Thử tạo thư mục thực tế trên đĩa cứng
        try:
            os.mkdir(target_abs)
            return True, R_250
        except Exception:
            return False, R_550

    def remove_dir(self, dir_name):
        """Xử lý lệnh RMD: Xóa thư mục rỗng"""
        # 1. Cho đường dẫn đi qua bộ lọc Sandbox
        is_safe, target_abs, _ = self._resolve_path(dir_name)
        
        # 2. Kiểm tra vi phạm Sandbox
        if not is_safe:
            return False, R_550

        # 3. Kiểm tra sự tồn tại
        if not os.path.exists(target_abs):
            return False, R_550

        # 4. Kiểm tra có phải là Thư mục hay không
        if not os.path.isdir(target_abs):
            return False, R_550

        # 5. Thử xóa thư mục bằng os.rmdir()
        try:
            os.rmdir(target_abs)
            return True, R_250
        except Exception:
            return False, R_550

