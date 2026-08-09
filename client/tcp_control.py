import socket


class TcpControlClient:
    """
    Client side: open a TCP connection to the server, send FTP commands, and receive replies.
    """

    host: str
    port: int
    sock: socket.socket | None

    def __init__(self, host: str, port: int = 21):
        self.host = host
        self.port = port
        self.sock = None

    def connect(self) -> str:
        """
        Connect to the server over TCP.
        Returns the first banner reply from the server (for example, "220 Service ready...").
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        return self.recv_reply()

    def _send_command(self, command: str) -> str:
        """
        Send one FTP command (no need to include \\r\\n; the method adds it automatically).
        Returns the full reply string from the server.
        """
        if self.sock:
            self.sock.sendall(f"{command}\r\n".encode("utf-8"))
        return self.recv_reply()

    def send_command(self, command: str) -> list[str]:
        """
        Send an FTP command and handle the full response cycle.
        Returns a list of replies (e.g. initial reply and completion reply if 1xx).
        """
        replies = []
        reply = self._send_command(command)
        if reply:
            replies.append(reply)
            if reply.strip().startswith("1"):
                # Wait for the completion reply
                reply2 = self.recv_reply()
                if reply2:
                    replies.append(reply2)
        return replies

    def recv_reply(self) -> str:
        """
        Read and assemble a reply from the server, including multi-line replies (NNN-...).
        Returns the full reply as a string.
        """
        buf = ""
        while self.sock:
            chunk = self.sock.recv(4096).decode("utf-8", errors="replace")
            if not chunk:
                break
            buf += chunk
            # Check for final reply line: 'NNN ' (no hyphen)
            lines = buf.split("\r\n")
            for line in lines:
                if len(line) >= 4 and line[3] == " " and line[:3].isdigit():
                    return buf.strip()
        return buf.strip()

    def get_code(self, reply: str) -> int:
        """Get 3 digit reply code from reply string."""
        return int(reply[:3]) if reply and reply[:3].isdigit() else 0

    def quit(self) -> None:
        """Send QUIT command and close the connection."""
        self.send_command("QUIT")
        self.close()

    def close(self) -> None:
        """Close the TCP connection."""
        if self.sock:
            self.sock.close()
            self.sock = None
