import os
import stat
import time


class DirWalker:
    """
    Duyệt thư mục tối ưu bằng os.scandir() và định dạng kết quả theo chuẩn Unix ls -l.
    Tương thích 100% với các Client FTP GUI (FileZilla, WinSCP, cURL).
    """

    @staticmethod
    def list_detailed(directory: str) -> str:
        """
        Trả chuỗi liệt kê chi tiết theo chuẩn Unix `ls -l` cho lệnh LIST.
        Định dạng: drwxr-xr-x 1 ftp ftp 4096 Jan 01 12:00 dirname
        """
        lines = []
        try:
            for entry in sorted(os.scandir(directory), key=lambda e: e.name):
                st = entry.stat(follow_symlinks=False)
                perm_str = stat.filemode(st.st_mode)
                nlink = getattr(st, "st_nlink", 1)
                size = st.st_size
                mtime = time.strftime("%b %d %H:%M", time.localtime(st.st_mtime))
                lines.append(f"{perm_str} {nlink:>2} ftp ftp {size:>12} {mtime} {entry.name}")
        except PermissionError:
            pass
        return "\r\n".join(lines)

    @staticmethod
    def list_names(directory: str) -> str:
        """
        Trả danh sách tên tập tin/thư mục thuần tuý cho lệnh NLST.
        """
        try:
            names = sorted(e.name for e in os.scandir(directory))
            return "\r\n".join(names)
        except PermissionError:
            return ""