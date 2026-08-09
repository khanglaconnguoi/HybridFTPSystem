"""
common/packet_format.py

Module quản lý định dạng gói tin (Packet Layout), đóng gói (pack) 
và bóc tách (unpack) dữ liệu RDT 3.0 over UDP.
"""

import struct
import binascii


FLAG_SYN  = 0b00000001   # Bắt đầu phiên
FLAG_ACK  = 0b00000010   # Đây là gói ACK
FLAG_FIN  = 0b00000100   # Kết thúc truyền
FLAG_DATA = 0b00001000   # Gói chứa dữ liệu
FLAG_NACK = 0b00010000   # Yêu cầu truyền lại (selective)

# Cấu trúc Header (15 Bytes):
# ! : Network byte order (Big-endian)
# I : unsigned int (4 bytes)  -> seq_num
# I : unsigned int (4 bytes)  -> ack_num
# B : unsigned char (1 byte)  -> flags
# I : unsigned int (4 bytes)  -> checksum (CRC32)
# H : unsigned short (2 bytes)-> payload_len
HEADER_FORMAT = "!IIBIH"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # Đúng 15 bytes


class UdpPacket:
    """
    Đóng gói/giải mã custom UDP header.
    Mọi dữ liệu truyền qua kênh UDP đều là UdpPacket.
    """
    __slots__ = ("seq_num", "ack_num", "flags", "checksum", "payload")

    def __init__(
        self,
        seq_num: int  = 0,
        ack_num: int  = 0,
        flags:   int  = 0,
        payload: bytes = b"",
        checksum: int | None = None,
    ):
        self.seq_num  = seq_num
        self.ack_num  = ack_num
        self.flags    = flags
        self.payload  = payload
        # Nếu không truyền checksum → tự tính (khi tạo gói mới)
        # Nếu truyền checksum  → dùng giá trị đó (khi unpack từ mạng)
        self.checksum = checksum if checksum is not None else self._calc_checksum()

    # ── Kiểm tra loại gói ──────────────────────────────────────
    @property
    def is_ack(self)  -> bool: return bool(self.flags & FLAG_ACK)
    @property
    def is_data(self) -> bool: return bool(self.flags & FLAG_DATA)
    @property
    def is_fin(self)  -> bool: return bool(self.flags & FLAG_FIN)
    @property
    def is_syn(self)  -> bool: return bool(self.flags & FLAG_SYN)

    # ── Kiểm tra tính toàn vẹn ─────────────────────────────────
    def is_valid(self) -> bool:
        return self.checksum == self._calc_checksum()

    def _calc_checksum(self) -> int:
        return binascii.crc32(self.payload) & 0xFFFF_FFFF

    # ── Serialisation ──────────────────────────────────────────
    def pack(self) -> bytes:
        header = struct.pack(
            "!IIBIH",
            self.seq_num,
            self.ack_num,
            self.flags,
            self.checksum,
            len(self.payload),
        )
        return header + self.payload

    @classmethod
    def unpack(cls, raw: bytes) -> "UdpPacket":
        seq, ack, flags, chk, pay_len = struct.unpack("!IIBIH", raw[:HEADER_SIZE])
        payload = raw[HEADER_SIZE : HEADER_SIZE + pay_len]
        return cls(seq_num=seq, ack_num=ack, flags=flags, payload=payload, checksum=chk)

    # ── Factory methods (tạo gói nhanh) ────────────────────────
    @classmethod
    def data_packet(cls, seq: int, payload: bytes) -> "UdpPacket":
        return cls(seq_num=seq, flags=FLAG_DATA, payload=payload)

    @classmethod
    def ack_packet(cls, ack: int) -> "UdpPacket":
        return cls(ack_num=ack, flags=FLAG_ACK)

    @classmethod
    def fin_packet(cls) -> "UdpPacket":
        return cls(flags=FLAG_FIN)

    @classmethod
    def syn_packet(cls) -> "UdpPacket":
        return cls(flags=FLAG_SYN)