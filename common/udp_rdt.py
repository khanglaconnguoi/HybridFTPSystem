# """
# common/udp_rdt.py
# ~~~~~~~~~~~~~~~~~

# Module quản lý kết nối Data Channel truyền dữ liệu tin cậy qua UDP (RDT 3.0).
# Bao gồm:
#   - RDTSender: Gửi file/bytes qua UDP với Sliding Window, Congestion Control & Fast Retransmit.
#   - RDTReceiver: Nhận file/bytes qua UDP, xử lý ACK và sắp xếp thứ tự gói tin (Selective ACK/Repeat).
#   - UDPRDTEngine: Class Facade cho Server Session xử lý các lệnh truyền dữ liệu (PASV, PORT, RETR, STOR, HASH, TYPE, MODE, ABOR).
# """

# import hashlib
# import io
# import logging
# import os
# import socket
# import threading
# import time
# from typing import Optional, Tuple, BinaryIO

# from common.rdt.packet_format import (
#     UdpPacket as PacketFormat,
#     FLAG_FIN,
#     FLAG_ACK,
#     FLAG_SYN,
#     FLAG_DATA,
# )
# from common.reply_codes import ReplyCode

# # ----------------------------------------------------------------------
# # 1. CONSTANTS & LOGGING
# # ----------------------------------------------------------------------
# CHUNK_SIZE: int = 1024
# DEFAULT_TIMEOUT: float = 0.5
# MAX_RETRIES: int = 5
# BUFFER_SIZE: int = 2048

# logger = logging.getLogger(__name__)


# # ----------------------------------------------------------------------
# # 2. CUSTOM EXCEPTIONS
# # ----------------------------------------------------------------------
# class SocketTransferError(Exception):
#     """Ngoại lệ chung cho lỗi truyền dữ liệu qua Socket."""
#     pass


# class SocketTimeoutError(SocketTransferError):
#     """Lỗi quá thời gian chờ (Timeout) trên Socket."""
#     pass


# class TransferAborted(SocketTransferError):
#     """Lỗi khi quá trình truyền bị hủy bởi lệnh ABOR từ client."""
#     pass





# class UDPRDTEngine:
#     """
#     Facade Class quản lý Data Channel và thực thi các lệnh FTP liên quan đến truyền dữ liệu.
#     Dùng chung cho cả Server và Client hoặc tích hợp vào CommandDispatcher.
#     """

#     def __init__(self, session = None) -> None:
#         self.session = session
#         self.transfer_type: str = 'I'
#         self.transfer_mode: str = 'S'
#         self.data_mode: str | None = None
#         self.data_sock: socket.socket | None = None
#         self.data_addr: Tuple[str, int] | None = None
#         self.abort_flag= threading.Event()

#     def _send_reply(self, reply_str: str) -> None:
#         """Phương thức phụ trợ gửi phản hồi về Session hoặc log nếu chạy riêng biệt."""
#         if self.session and hasattr(self.session, "send_reply"):
#             self.session.send_reply(reply_str)
#         else:
#             logger.info(f"[Control Reply] {reply_str.strip()}")

#     # HANDLERS
#     def handle_type(self, arg: str) -> None:
#         """
#         [Lệnh TYPE] Thiết lập kiểu truyền dữ liệu (I = Image/Binary, A = ASCII).
#         """
#         arg_upper = arg.strip().upper()
#         if arg_upper in ('I', 'A'):
#             self.transfer_type = arg_upper
#             logger.info(f"Đã chuyển kiểu truyền (TYPE) thành: {self.transfer_type}")
#             self._send_reply(ReplyCode.COMMAND_OK.format(f"Type set to {self.transfer_type}."))
#         else:
#             logger.warning(f"Lỗi lệnh TYPE: Tham số không hợp lệ '{arg}'")
#             self._send_reply(ReplyCode.PARAM_NOT_IMPLEMENTED.format())

#     def handle_mode(self, arg: str) -> None:
#         """
#         [Lệnh MODE] Thiết lập chế độ truyền dữ liệu (S = Stream).
#         """
#         arg_upper = arg.strip().upper()
#         if arg_upper == 'S':
#             self.transfer_mode = arg_upper
#             logger.info(f"Đã chuyển chế độ truyền (MODE) thành: {self.transfer_mode}")
#             self._send_reply(ReplyCode.COMMAND_OK.format(f"Mode set to {self.transfer_mode}."))
#         else:
#             logger.warning(f"Lỗi lệnh MODE: Tham số không hợp lệ '{arg}'")
#             self._send_reply(ReplyCode.PARAM_NOT_IMPLEMENTED.format())

#     def handle_pasv(self, _arg: str = "") -> None:
#         """
#         [Lệnh PASV] Mở UDP socket ngẫu nhiên trên Server và trả về địa chỉ cho Client.
#         """
#         try:
#             self.data_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#             self.data_sock.bind(("", 0))
#             port = self.data_sock.getsockname()[1]
#             self.data_mode = 'PASV'

#             if self.session and hasattr(self.session, "conn"):
#                 ip = self.session.conn.getsockname()[0]
#                 if ip == "0.0.0.0" or ip == "::":
#                     ip = "127.0.0.1"
#             else:
#                 ip = "127.0.0.1"

#             ip_parts = ip.split(".")
#             p1, p2 = port >> 8, port & 0xFF  # p1 = 8 bit đầu, p2 = 8 bit sau của port
#             logger.info(f"Mở PASV mode thành công: bind port {port}")

#             self._send_reply(
#                 ReplyCode.ENTERING_PASSIVE.format(
#                     h1=ip_parts[0],
#                     h2=ip_parts[1],
#                     h3=ip_parts[2],
#                     h4=ip_parts[3],
#                     p1=p1,
#                     p2=p2
#                 )
#             )

#         except Exception as err:
#             logger.error(f"Lỗi khi khởi tạo PASV mode: {err}")
#             self._send_reply(ReplyCode.CANT_OPEN_DATA_CONN.format("Cannot open passive data connection."))

#     def handle_port(self, arg: str = "") -> None:
#         """
#         [Lệnh PORT] Nhận địa chỉ IP và Port từ Client (Active mode).
#         Dạng tham số: h1,h2,h3,h4,p1,p2
#         """
#         try:
#             parts = [p.strip() for p in arg.split(",")]
#             if len(parts) != 6:
#                 logger.warning(f"Lỗi cú pháp lệnh PORT: Tham số không đủ 6 phần ({arg})")
#                 self._send_reply(ReplyCode.SYNTAX_ERROR_PARAM.format("Syntax error in PORT parameters."))
#                 return

#             ip = '.'.join(parts[:4])
#             port = (int(parts[4]) << 8) + int(parts[5])

#             self.data_mode = 'PORT'
#             self.data_addr = (ip, port)
#             logger.info(f"Đã lưu cấu hình PORT active mode: {ip}:{port}")
#             self._send_reply(ReplyCode.COMMAND_OK.format("PORT command successful."))

#         except Exception as err:
#             logger.error(f"Lỗi khi xử lý lệnh PORT ({arg}): {err}")
#             self._send_reply(ReplyCode.SYNTAX_ERROR_PARAM.format("Invalid PORT parameters."))

#     # def handle_retr(self, filename: str) -> None:
#     #     """
#     #     [Lệnh RETR] Gửi file từ Server về Client qua UDP RDT.
#     #     """

#     # def handle_stor(self, filename: str) -> None:
#     #     """
#     #     [Lệnh STOR] Nhận file từ Client về Server qua UDP RDT.
#     #     """

#     # def handle_hash(self, filename: str) -> None:
#     #     """
#     #     [Lệnh HASH] Tính toán mã SHA-256 của file trên Server để kiểm tra tính toàn vẹn.
#     #     """
#     #     target_path = self._resolve_file_path(filename)
#     #     if not target_path or not os.path.isfile(target_path):
#     #         #self._send_reply("550 File unavailable.\r\n")
#     #         return

#     #     try:
#     #         sha256 = hashlib.sha256()
#     #         with open(target_path, "rb") as f:
#     #             while chunk := f.read(4096):
#     #                 sha256.update(chunk)
#     #         file_hash = sha256.hexdigest()
#     #         #self._send_reply(f"213 SHA-256 {file_hash}\r\n")

#     #     except Exception as err:
#     #         logger.error(f"Lỗi khi tính HASH ({filename}): {err}")
#     #         #self._send_reply("550 Failed to compute hash.\r\n")

#     def handle_abor(self, _arg: str = "") -> None:
#         """
#         [Lệnh ABOR] Hủy bỏ quá trình truyền file đang diễn ra.
#         """
#         self.abort_flag.set()
#         logger.info("Đã bật cờ hủy truyền dữ liệu (ABOR).")

#         if self.data_sock and self.data_addr:
#             try:
#                 rst_packet = PacketFormat.make_rst()
#                 self.data_sock.sendto(rst_packet, self.data_addr)
#                 logger.info(f"Đã gửi gói RST đến {self.data_addr} để ngắt truyền dữ liệu.")
#             except Exception as e:
#                 logger.error(f"Lỗi khi gửi gói RST cho lệnh ABOR: {e}")

#         self._send_reply(ReplyCode.TRANSFER_COMPLETE.format("ABOR command successful."))






