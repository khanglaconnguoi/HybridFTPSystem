import os
import sys
import stat
import time


class ClientSession:
    pass
# Thêm thư mục gốc vào sys.path để có thể import từ folder 'common'
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

import common.reply_codes 

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
        try:
            # BƯỚC 1: Xử lý điểm bắt đầu 
            if requested_path.startswith("/") or requested_path.startswith("\\"):
                combined = os.path.join(self.root_dir, requested_path.lstrip("/\\"))
            else:
                curr_abs = os.path.join(self.root_dir, self.current_rel_path.lstrip("/\\"))
                combined = os.path.join(curr_abs, requested_path)

            # BƯỚC 2: Phân giải thành Đường dẫn Tuyệt đối Thật trên đĩa
            target_abs = os.path.abspath(combined)

            # BƯỚC 3: Kiểm tra Rào chắn Sandbox (Anti Path Traversal)
            is_safe = os.path.commonpath([self.root_dir, target_abs]) == self.root_dir
            if not is_safe:
                return False, target_abs, self.current_rel_path

            # BƯỚC 4: Tính lại Đường dẫn Ảo mới cho Client
            rel_path = os.path.relpath(target_abs, self.root_dir)
            
            if rel_path == ".":
                new_virtual_path = "/"
            else:
                new_virtual_path = "/" + rel_path.replace("\\", "/")

            return True, target_abs, new_virtual_path
        except (ValueError, Exception):
            return False, "", self.current_rel_path

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
        
        # 2. Kiểm tra vi phạm Sandbox hoặc không phải Thư mục
        if not is_safe or not os.path.exists(target_abs) or not os.path.isdir(target_abs):
            return False, R_550

        # 5. Thử xóa thư mục bằng os.rmdir()
        try:
            os.rmdir(target_abs)
            return True, R_250
        except Exception:
            return False, R_550

    def get_nlst(self, target_dir=""):
        """Xử lý lệnh NLST: Trả về danh sách tên file/folder"""
        # 1. Cho đường dẫn đi qua bộ lọc Sandbox
        is_safe, target_abs, _ = self._resolve_path(target_dir)

        # 2. Kiểm tra vi phạm Sandbox / không phải Thư mục / không có quyền đọc (os.R_OK)
        if not is_safe or not os.path.exists(target_abs) or not os.path.isdir(target_abs):
            return False, R_550
        if not os.access(target_abs, os.R_OK):
            return False, R_550

        # 3. Lấy danh sách file/folder với bẫy ngoại lệ
        try:
            names = os.listdir(target_abs)
            if not names:
                return True, ""
            data_str = "\r\n".join(names) + "\r\n"
            return True, data_str
        except Exception:
            return False, R_550

    def get_list(self, target_dir=""):
        """Xử lý lệnh LIST: Trả về danh sách chi tiết (name, size, type, permissions)"""
        # 1. Cho đường dẫn đi qua bộ lọc Sandbox
        is_safe, target_abs, _ = self._resolve_path(target_dir)

        # 2. Kiểm tra vi phạm Sandbox / không phải Thư mục / không có quyền đọc (os.R_OK)
        if not is_safe or not os.path.exists(target_abs) or not os.path.isdir(target_abs):
            return False, R_550
        if not os.access(target_abs, os.R_OK):
            return False, R_550

        # 3. Lấy danh sách các mục với bẫy ngoại lệ
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
            return False, R_550

    def get_size(self, target_dir=""):
        """Xử lý lệnh SIZE: Trả về độ lớn của File"""
        # 1. Cho đường dẫn đi qua bộ lọc Sandbox
        is_safe, target_abs, _ = self._resolve_path(target_dir)

        # 2. Kiểm tra vi phạm Sandbox / File không tồn tại / Không phải là File / không có quyền đọc
        if not is_safe or not os.path.exists(target_abs) or not os.path.isfile(target_abs):
            return False, R_550
        if not os.access(target_abs, os.R_OK):
            return False, R_550

        # 3. Lấy dung lượng file bằng os.stat().st_size với bẫy ngoại lệ
        try:
            size = os.stat(target_abs).st_size
            return True, R_213.format(size=size)
        except Exception:
            return False, R_550

    def get_mdtm(self, target_dir=""):
        """Xử lý lệnh MDTM: Trả về mốc thời gian sửa đổi lần cuối của tập tin (định dạng YYYYMMDDHHMMSS)"""
        # 1. Cho đường dẫn đi qua bộ lọc Sandbox
        is_safe, target_abs, _ = self._resolve_path(target_dir)

        # 2. Kiểm tra vi phạm Sandbox / File không tồn tại / Không phải là File / không có quyền đọc
        if not is_safe or not os.path.exists(target_abs) or not os.path.isfile(target_abs):
            return False, R_550
        if not os.access(target_abs, os.R_OK):
            return False, R_550

        # 3. Lấy mốc thời gian sửa đổi tập tin và định dạng theo chuẩn UTC YYYYMMDDHHMMSS
        try:
            mtime = os.path.getmtime(target_abs)
            mtime_str = time.strftime("%Y%m%d%H%M%S", time.gmtime(mtime))
            return True, R_213.format(size=mtime_str)
        except Exception:
            return False, R_550

    def set_dele(self,target_dir=""):
        # 1. Cho đường dẫn đi qua bộ lọc Sandbox
        is_safe, target_abs, _ = self._resolve_path(target_dir)

        # 2. Kiểm tra vi phạm Sandbox / File không tồn tại / Không phải là File / không có quyền ghi (os.W_OK)
        if not is_safe or not os.path.exists(target_abs) or not os.path.isfile(target_abs):
            return False, R_550
        if not os.access(target_abs, os.W_OK):
            return False, R_550

        # 3. Xóa tập tin bằng os.remove() với bẫy ngoại lệ
        try:
            os.remove(target_abs)
            return True, R_250
        except Exception:
            return False, R_550
    
    def set_stou(self, target_dir="file.tmp"):
    # 1. Cho đường dẫn đi qua bộ lọc Sandbox
        is_safe, target_abs, _ = self._resolve_path(target_dir)
        if not is_safe:
            return False, R_550

        # 2. Thuật toán sinh tên file độc nhất nếu bị trùng
        base_dir = os.path.dirname(target_abs)
        filename = os.path.basename(target_abs)
        name, ext = os.path.splitext(filename)
        
        if not name:
            name, ext = "file", ".tmp"

        unique_abs = target_abs
        counter = 1

        # Lặp lại cho đến khi tìm được đường dẫn chưa tồn tại
        while os.path.exists(unique_abs):
            unique_name = f"{name}_{counter}{ext}"
            unique_abs = os.path.join(base_dir, unique_name)
            counter += 1

        # 3. Tạo file rỗng giữ chỗ trên đĩa
        try:
            with open(unique_abs, "xb") as f:
                pass  # Tạo file rỗng 0-byte
            
            return True, R_250
        except Exception:
            return False, R_550
            
    def set_appe(self, target_dir=""):
        """Xử lý chuẩn bị cho lệnh APPE: Nối thêm dữ liệu vào cuối file"""
        # 1. Cho đường dẫn đi qua bộ lọc Sandbox
        is_safe, target_abs, _ = self._resolve_path(target_dir)
        if not is_safe:
            return False, R_550

        # 2. Trường hợp 1: File đã tồn tại -> Kiểm tra phải là file chuẩn và có quyền ghi
        if os.path.exists(target_abs):
            if not os.path.isfile(target_abs) or not os.access(target_abs, os.W_OK):
                return False, R_550
        else:
            # Trường hợp 2: File chưa tồn tại -> Kiểm tra thư mục cha có quyền tạo/ghi file không
            parent_dir = os.path.dirname(target_abs)
            if not os.path.exists(parent_dir) or not os.access(parent_dir, os.W_OK):
                return False, R_550

        # 3. Trả về đường dẫn tuyệt đối thành công để Server mở file chế độ 'ab'
        return True, R_150, target_abs


    def set_rnfr(self,target_dir=""):
        # 1. Cho đường dẫn đi qua bộ lọc Sandbox
        is_safe, target_abs, _ = self._resolve_path(target_dir)
        if not is_safe or not os.path.exists(target_abs):
            return False, R_550
        return True,R_350, target_abs            

    def set_rnto(self, old_file_path, new_name):
        """Xử lý bước 2 của đổi tên (RNTO): Đổi tên file/folder thật trên đĩa"""
        try:
            # 1. Kiểm tra nếu chưa từng gọi lệnh RNFR trước đó
            if not old_file_path or not os.path.exists(old_file_path):
                return False, R_503

            # 2. Kiểm tra nếu Client quên nhập tên mới
            if not new_name:
                return False, R_550
            
            # 3. Cho tên mới đi qua bộ lọc Sandbox
            is_safe, new_abs, _ = self._resolve_path(new_name)
            if not is_safe:
                return False, R_550

            # 4. Kiểm tra nếu tên mới đã tồn tại trên đĩa (tránh ghi đè trùng tên)
            if os.path.exists(new_abs):
                return False, R_550
            
            # 5. Thực hiện đổi tên đĩa cứng thật
            os.rename(old_file_path, new_abs)
            return True, R_250

        except Exception:
            return False, R_550

