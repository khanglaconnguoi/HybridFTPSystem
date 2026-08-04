import socket


class TcpControlClient:
    """
    Client side: open a TCP connection to the server, send FTP commands, and receive replies.
    """

    host: str
    port: int
    sock: socket.socket

    def __init__(self, host: str, port: int = 21): ...

    def connect(self) -> str:
        """
        Connect to the server over TCP.
        Returns the first banner reply from the server (for example, \"220 Service ready...\").
        """
        raise NotImplementedError

    def send_command(self, command: str) -> str:
        """
        Send one FTP command (no need to include \\r\\n; the method adds it automatically).
        Returns the full reply string from the server.
        """
        raise NotImplementedError

    def recv_reply(self) -> str:
        """
        Read and assemble a reply from the server, including multi-line replies (NNN-...).
        Returns the full reply as a string.
        """
        raise NotImplementedError

    def close(self) -> None:
        """Close the TCP connection."""
        raise NotImplementedError
