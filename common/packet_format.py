"""
common/packet_format.py

Module quản lý định dạng gói tin (Packet Layout), đóng gói (pack) 
và bóc tách (unpack) dữ liệu RDT 3.0 over UDP.
"""

import struct
import zlib
from dataclasses import dataclass
from typing import Tuple


FLAG_FIN  = 0x01  # Bit 0: 0000 0001 -> Kết thúc truyền file (Teardown)
FLAG_ACK  = 0x02  # Bit 1: 0000 0010 -> Xác nhận gói tin (ACK)
FLAG_SYN  = 0x04  # Bit 2: 0000 0100 -> Bắt tay kết nối (Handshake)
FLAG_RST  = 0x08  # Bit 3: 0000 1000 -> Hủy truyền đột ngột (Lệnh ABOR)
FLAG_DATA = 0x10  # Bit 4: 0001 0000 -> Gói tin chứa dữ liệu

# Cấu trúc Header (15 Bytes):
# ! : Network byte order (Big-endian)
# I : unsigned int (4 bytes)  -> seq_num
# I : unsigned int (4 bytes)  -> ack_num
# B : unsigned char (1 byte)  -> flags
# I : unsigned int (4 bytes)  -> checksum (CRC32)
# H : unsigned short (2 bytes)-> payload_len
HEADER_FORMAT = "!IIBIH"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # Đúng 15 bytes


@dataclass
class PacketHeader:
    """Chứa dữ liệu Header đã được giải mã từ bytes thô."""
    seq_num: int
    ack_num: int
    flags: int
    checksum: int
    payload_len: int


class PacketFormat:
    """Cung cấp các phương thức tĩnh phục vụ xử lý gói tin RDT."""

    @staticmethod
    def calculate_checksum(payload: bytes) -> int:
        """Tính toán mã CRC32 của phần Payload (trả về số nguyên 32-bit)."""
        return zlib.crc32(payload) & 0xFFFFFFFF

    @classmethod
    def pack(
        cls, 
        seq_num: int, 
        ack_num: int, 
        flags: int, 
        payload: bytes = b""
    ) -> bytes:
        """
        Đóng gói thông tin Header và Payload thành chuỗi bytes thô để gửi qua UDP Socket.
        """
        payload_len = len(payload)
        checksum = cls.calculate_checksum(payload)

        # Đóng gói 15 bytes Header
        header_bytes = struct.pack(
            HEADER_FORMAT,
            seq_num,
            ack_num,
            flags,
            checksum,
            payload_len
        )

        # Ghép Header + Payload
        return header_bytes + payload

    @classmethod
    def unpack(cls, raw_data: bytes) -> Tuple[PacketHeader, bytes]:
        """
        Bóc tách chuỗi bytes thô từ Socket thành đối tượng PacketHeader và Payload bytes.
        """
        if len(raw_data) < HEADER_SIZE:
            raise ValueError(
                f"Gói tin bị thiếu ({len(raw_data)} bytes), nhỏ hơn kích thước Header tối thiểu ({HEADER_SIZE} bytes)."
            )

        # Unpack header từ binary
        seq_num, ack_num, flags, checksum, payload_len = struct.unpack(
            HEADER_FORMAT, raw_data[:HEADER_SIZE]
        )

        if len(raw_data) < HEADER_SIZE + payload_len:
            raise ValueError(
                f"Gói tin bị cắt xén ({len(raw_data)} bytes), kỳ vọng tối thiểu ({HEADER_SIZE + payload_len} bytes)."
            )

        # Tách chính xác payload dựa trên payload_len
        payload = raw_data[HEADER_SIZE : HEADER_SIZE + payload_len]

        header = PacketHeader(
            seq_num=seq_num,
            ack_num=ack_num,
            flags=flags,
            checksum=checksum,
            payload_len=payload_len
        )

        return header, payload

    @classmethod
    def verify_checksum(cls, raw_data: bytes) -> bool:
        """
        Kiểm tra tính toàn vẹn của gói tin bằng cách tính lại CRC32 Payload 
        và so sánh với Checksum trong Header.
        """
        if len(raw_data) < HEADER_SIZE:
            return False

        try:
            header, payload = cls.unpack(raw_data)
            expected_checksum = cls.calculate_checksum(payload)
            return header.checksum == expected_checksum
        except Exception:
            return False

    # --- Helper Factories ---
    @classmethod
    def make_data(cls, seq_num: int, payload: bytes) -> bytes:
        """Tạo gói tin DATA."""
        return cls.pack(seq_num=seq_num, ack_num=0, flags=FLAG_DATA, payload=payload)

    @classmethod
    def make_ack(cls, ack_num: int) -> bytes:
        """Tạo gói tin ACK."""
        return cls.pack(seq_num=0, ack_num=ack_num, flags=FLAG_ACK, payload=b"")

    @classmethod
    def make_syn(cls, seq_num: int = 0) -> bytes:
        """Tạo gói tin SYN (Handshake)."""
        return cls.pack(seq_num=seq_num, ack_num=0, flags=FLAG_SYN, payload=b"")

    @classmethod
    def make_fin(cls, seq_num: int) -> bytes:
        """Tạo gói tin FIN (Kết thúc)."""
        return cls.pack(seq_num=seq_num, ack_num=0, flags=FLAG_FIN, payload=b"")

    @classmethod
    def make_rst(cls, seq_num: int = 0) -> bytes:
        """Tạo gói tin RST (Hủy truyền)."""
        return cls.pack(seq_num=seq_num, ack_num=0, flags=FLAG_RST, payload=b"")