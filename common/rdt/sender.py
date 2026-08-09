import socket
import threading
import time
from common.constants import CHUNK_SIZE, WINDOW_SIZE, TIMEOUT, MAX_RETRY
from common.rdt.packet_format import UdpPacket, HEADER_SIZE

class RdtSender:
    """
    Gửi dữ liệu qua UDP với cơ chế Selective Repeat.
    - Sliding window: gửi WINDOW_SIZE gói trước khi chờ
    - Timer riêng cho từng gói (Selective Repeat)
    - Fast retransmit khi nhận 3 ACK trùng
    - Congestion control: slow start + congestion avoidance
    """

    def __init__(self, sock: socket.socket, peer_addr: tuple):
        self._sock      = sock
        self._peer      = peer_addr
        self._lock      = threading.Lock()

        # Congestion control
        self._cwnd      = 1        # Congestion window (gói)
        self._ssthresh  = 16       # Slow start threshold
        self._dup_ack   = {}       # ack_num → count (fast retransmit)

    # ── Public API ─────────────────────────────────────────────

    def send_bytes(self, data: bytes) -> bool:
        """
        Gửi toàn bộ data. Trả True nếu thành công, False nếu thất bại.
        Đây là method duy nhất bên ngoài cần gọi.
        """
        if self._peer is None:
            self._sock.settimeout(10.0)
            try:
                raw, addr = self._sock.recvfrom(2048)
                packet = UdpPacket.unpack(raw)
                if packet.is_syn:
                    self._peer = addr
                else:
                    return False
            except socket.timeout:
                return False
            except Exception:
                return False

        chunks = [data[i : i + CHUNK_SIZE] for i in range(0, len(data), CHUNK_SIZE)]
        total  = len(chunks)
        window = {}   # seq → (packet, send_time, retry_count)
        base   = 0    # seq nhỏ nhất chưa được ACK
        next_s = 0    # seq tiếp theo cần gửi

        while base < total:
            # Gửi các gói trong cửa sổ
            win_size = min(int(self._cwnd), WINDOW_SIZE)
            while next_s < total and next_s < base + win_size:
                packet = UdpPacket.data_packet(next_s, chunks[next_s])
                self._sock.sendto(packet.pack(), self._peer)
                window[next_s] = (packet, time.monotonic(), 0)
                next_s += 1

            # Chờ ACK
            try:
                self._sock.settimeout(TIMEOUT)
                raw, _ = self._sock.recvfrom(HEADER_SIZE + 4)
                ack_packet = UdpPacket.unpack(raw)
                if not ack_packet.is_ack or not ack_packet.is_valid():
                    continue
                ack_num = ack_packet.ack_num

                # Cumulative ACK — gói ≤ ack_num đã nhận
                if ack_num > base:
                    for s in range(base, ack_num):
                        window.pop(s, None)
                    base = ack_num
                    self._on_ack()
                    self._dup_ack = {k: v for k, v in self._dup_ack.items() if k >= base}

                # Fast retransmit
                self._dup_ack[ack_num] = self._dup_ack.get(ack_num, 0) + 1
                if self._dup_ack[ack_num] == 3 and ack_num in window:
                    packet, _, retry = window[ack_num]
                    self._sock.sendto(packet.pack(), self._peer)
                    window[ack_num] = (packet, time.monotonic(), retry + 1)
                    self._on_loss()

            except socket.timeout:
                # Timeout — retransmit tất cả gói trong window chưa ACK
                if base in window:
                    packet, t, retry = window[base]
                    if retry >= MAX_RETRY:
                        return False 
                    self._sock.sendto(packet.pack(), self._peer)
                    window[base] = (packet, time.monotonic(), retry + 1)
                    self._on_loss()
                # now = time.monotonic()
                # for seq, (packet, t, retry) in list(window.items()):
                #     if now - t > TIMEOUT:
                #         if retry >= MAX_RETRY:
                #             return False  # Từ bỏ sau MAX_RETRY lần
                #         self._sock.sendto(packet.pack(), self._peer)
                #         window[seq] = (packet, now, retry + 1)
                # self._on_loss()

        # Gửi FIN để báo kết thúc
        fin_packet = UdpPacket.fin_packet()
        for _ in range(MAX_RETRY):
            self._sock.sendto(fin_packet.pack(), self._peer)
            try:
                self._sock.settimeout(TIMEOUT)
                raw, _ = self._sock.recvfrom(HEADER_SIZE + 4)
                ack_pkt = UdpPacket.unpack(raw)
                if ack_pkt.is_ack and ack_pkt.is_valid():
                    break  # Receiver đã xác nhận FIN
            except socket.timeout:
                continue
        return True

    # ── Congestion control ─────────────────────────────────────

    def _on_ack(self) -> None:
        """Tăng cwnd: slow start hoặc congestion avoidance."""
        if self._cwnd < self._ssthresh:
            self._cwnd = min(self._cwnd * 1, WINDOW_SIZE)   # Slow start
        else:
            self._cwnd = min(self._cwnd + 1, WINDOW_SIZE)   # CA

    def _on_loss(self) -> None:
        """Giảm cwnd khi phát hiện mất gói."""
        self._ssthresh = max(int(self._cwnd / 2), 1)
        self._cwnd = 1   # Reset về slow start
