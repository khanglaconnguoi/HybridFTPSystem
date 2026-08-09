import socket
from common.rdt.sender   import RdtSender
from common.rdt.receiver import RdtReceiver

class DataChannelClient:
    """
    Phía client của kênh data UDP.
    Phối hợp với TcpControlClient: PASV/PORT negotiation
    → mở socket UDP → dùng RdtSender/Receiver.
    """

    def __init__(self):
        self._udp_sock: socket.socket | None = None
        self._server_data_addr: tuple | None = None

    def setup_from_pasv_reply(self, pasv_reply: str) -> bool:
        """
        Parse reply PASV '227 Entering Passive Mode (h1,h2,h3,h4,p1,p2).'
        Tạo UDP socket và lưu địa chỉ server.
        """
        try:
            start = pasv_reply.index("(") + 1
            end   = pasv_reply.index(")")
            parts = pasv_reply[start:end].split(",")
            ip    = ".".join(parts[:4])
            port  = (int(parts[4]) << 8) + int(parts[5])
            self._server_data_addr = (ip, port)
            self._udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._udp_sock.bind(("", 0))
            return True
        except (ValueError, IndexError):
            return False

    def upload(self, data: bytes) -> bool:
        """Gửi data tới server qua RDT."""
        if not self._udp_sock or not self._server_data_addr:
            return False
        sender = RdtSender(self._udp_sock, self._server_data_addr)
        return sender.send_bytes(data)

    def download(self) -> bytes | None:
        """Nhận data từ server qua RDT."""
        if not self._udp_sock:
            return None
            
        if self._server_data_addr:
            from common.rdt.packet_format import UdpPacket
            syn = UdpPacket.syn_packet()
            self._udp_sock.sendto(syn.pack(), self._server_data_addr)
            
        receiver = RdtReceiver(self._udp_sock)
        peer_ip  = self._server_data_addr[0] if self._server_data_addr else None
        peer     = (peer_ip, None) if peer_ip else None
        return receiver.receive_bytes(peer)

    def close(self) -> None:
        if self._udp_sock:
            self._udp_sock.close()
            self._udp_sock = None
