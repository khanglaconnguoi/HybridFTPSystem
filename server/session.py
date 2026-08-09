import socket
from enum import Enum, auto
from typing import Optional

from common.tcp_message_format import serialize_message


class AuthState(Enum):
    ANONYMOUS = auto()  # USER has not been sent yet
    USER_OK = auto()  # USER received, waiting for PASS
    LOGGED_IN = auto()  # Authentication successful


class ClientSession:
    """Stores all state for one client connection. Each client gets its own instance."""

    # Connection state (Module A)
    conn: socket.socket
    addr: tuple[str, int]
    host: str
    port: int

    # Authentication state (Module A)
    auth_state: AuthState
    username: Optional[str]

    # Directory state (Module C)
    sandbox_root: str
    cwd: str

    # Transfer configuration (Module B)
    transfer_type: str  # 'A' = ASCII, 'I' = Binary
    transfer_mode: str  # 'S' = Stream, 'B' = Block, 'C' = Compressed
    data_channel_mode: str  # 'PORT' or 'PASV'
    data_port: Optional[int]
    data_addr: Optional[tuple[str, int]]
    rdt_window: dict

    # Pending state (Module C)
    rename_pending: Optional[str]  # Stores the old name while waiting for RNTO

    def __init__(self, conn: socket.socket, addr: tuple[str, int], sandbox_root: str):
        self.conn = conn
        self.addr = addr
        try:
            self.host, self.port = addr
        except Exception as _e:
            self.host = ""
            self.port = 0

        # Authentication state (Module A)
        self.auth_state = AuthState.ANONYMOUS
        self.username = None

        # Directory state (Module C)
        self.sandbox_root = sandbox_root
        self.cwd = "/"

        # Transfer configuration (Module B)
        self.transfer_type = "I"  # 'A' or 'I'
        self.transfer_mode = "S"  # 'S', 'B', 'C'
        self.data_channel_mode = "PASV"  # 'PORT' or 'PASV'
        self.data_port = None
        self.data_addr = None
        self.rdt_window = {}

        # Pending state (Module C)
        self.rename_pending = None

    def send_reply(self, reply_line: str) -> None:
        """Send one FTP reply line back to the client over the TCP control socket."""
        data = serialize_message(reply_line)
        self.conn.sendall(data)

    def is_logged_in(self) -> bool:
        """Return True if the client has authenticated successfully."""
        return self.auth_state == AuthState.LOGGED_IN
