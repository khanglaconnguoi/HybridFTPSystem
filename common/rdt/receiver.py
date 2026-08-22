import socket
from typing import Callable
from common.constants import CHUNK_SIZE
from common.rdt.packet_format import UdpPacket, HEADER_SIZE

RECV_BUF = HEADER_SIZE + CHUNK_SIZE + 128  # header + max payload + buffer

class RdtReceiver:
    """
    Nhận dữ liệu UDP theo Selective Repeat.
    - Buffer out-of-order packets
    - Loại bỏ duplicate (seq đã nhận)
    - Gửi cumulative ACK
    - Phát hiện lỗi checksum → không ACK → sender sẽ timeout
    """

    def __init__(self, sock: socket.socket):
        self._sock = sock

    def receive_bytes(
        self,
        peer_addr: tuple | None = None,
        expected_total: int | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> bytes | None:
        """
        Nhận toàn bộ dữ liệu cho đến khi gặp FIN.
        peer_addr: nếu set, chỉ nhận từ địa chỉ đó (PASV mode).
        expected_total: tổng số bytes dự kiến (để hiển thị progress bar).
        on_progress: hàm callback (transferred, total) -> None.
        Trả bytes nếu thành công, None nếu lỗi.
        """
        buffer:  dict[int, bytes] = {}   # seq → payload
        received_seq: set[int]        = set()
        received_bytes = 0
        expected_seq = 0  # seq số tiếp theo cần đề ghép vào stream

        if on_progress and expected_total is not None:
            on_progress(0, expected_total)

        self._sock.settimeout(10.0)  # Timeout toàn phiên nhận

        try:
            while True:
                raw, addr = self._sock.recvfrom(RECV_BUF)

                # Lọc địa chỉ nếu cần (Passive mode)
                if peer_addr and addr[0] != peer_addr[0]:
                    continue

                packet = UdpPacket.unpack(raw)

                # Kiểm tra FIN
                if packet.is_fin:
                    fin_ack = UdpPacket.ack_packet(expected_seq)
                    self._sock.sendto(fin_ack.pack(), addr)
                    
                    result = b""
                    for seq in sorted(buffer.keys()):
                        result += buffer[seq]
                    if on_progress and expected_total is not None:
                        on_progress(len(result), expected_total)
                    return result

                # Bỏ qua gói không phải DATA
                if not packet.is_data:
                    continue

                # Kiểm tra checksum — nếu sai, im lặng (không ACK)
                if not packet.is_valid():
                    continue

                seq = packet.seq_num

                # Loại bỏ duplicate
                if seq not in received_seq:
                    buffer[seq]   = packet.payload
                    received_seq.add(seq)
                    received_bytes += len(packet.payload)
                    if on_progress and expected_total is not None:
                        on_progress(min(received_bytes, expected_total), expected_total)

                # Tính cumulative ACK = seq liên tục lớn nhất + 1
                cum_ack = expected_seq
                while cum_ack in received_seq:
                    cum_ack += 1
                expected_seq = cum_ack

                # Gửi ACK
                ack = UdpPacket.ack_packet(cum_ack)
                self._sock.sendto(ack.pack(), addr)

        except socket.timeout:
            return None
