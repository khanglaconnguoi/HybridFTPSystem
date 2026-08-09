import socket
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from common.tcp_message_format import serialize_message


class AuthState(Enum):
    ANONYMOUS = auto()  # USER has not been sent yet
    USER_OK = auto()  # USER received, waiting for PASS
    LOGGED_IN = auto()  # Authentication successful


@dataclass
class DataConfig:
    """Stores data channel transfer configuration for a client session."""

    transfer_type: str = "I"  # 'A' = ASCII, 'I' = Binary
    transfer_mode: str = "S"  # 'S' = Stream, 'B' = Block, 'C' = Compressed
    mode: str = "PASV"  # 'PORT' or 'PASV'
    client_data_addr: Optional[tuple[str, int]] = None
    server_data_port: Optional[int] = None


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
    data_config: DataConfig
    rdt_window: dict
    transfer_active: bool

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
        self.data_config = DataConfig()
        self.rdt_window = {}
        self.transfer_active = False

        # Pending state (Module C)
        self.rename_pending = None

    @property
    def transfer_type(self) -> str:
        return self.data_config.transfer_type

    @transfer_type.setter
    def transfer_type(self, value: str) -> None:
        self.data_config.transfer_type = value

    @property
    def transfer_mode(self) -> str:
        return self.data_config.transfer_mode

    @transfer_mode.setter
    def transfer_mode(self, value: str) -> None:
        self.data_config.transfer_mode = value

    @property
    def data_channel_mode(self) -> str:
        return self.data_config.mode

    @data_channel_mode.setter
    def data_channel_mode(self, value: str) -> None:
        self.data_config.mode = value

    @property
    def data_port(self) -> Optional[int]:
        return self.data_config.server_data_port

    @data_port.setter
    def data_port(self, value: Optional[int]) -> None:
        self.data_config.server_data_port = value

    @property
    def data_addr(self) -> Optional[tuple[str, int]]:
        return self.data_config.client_data_addr

    @data_addr.setter
    def data_addr(self, value: Optional[tuple[str, int]]) -> None:
        self.data_config.client_data_addr = value

    def send_reply(self, reply_line: str) -> None:
        """Send one FTP reply line back to the client over the TCP control socket."""
        data = serialize_message(reply_line)
        self.conn.sendall(data)

    def is_logged_in(self) -> bool:
        """Return True if the client has authenticated successfully."""
        return self.auth_state == AuthState.LOGGED_IN

