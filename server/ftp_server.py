import socket
import threading

from common.reply_codes import ReplyCode
from common.tcp_message_format import deserialize_message
from server.command_dispatcher import CommandDispatcher
from server.session import ClientSession

SESSION_TIMEOUT_SECONDS = 300.0


class FtpServer:
    """
    Listens for new TCP connections and handles each client independently.
    """

    host: str
    port: int
    sandbox_root: str
    active_sessions: dict[tuple, ClientSession]
    listening_socket: socket.socket

    def __init__(self, host: str, port: int, sandbox_root: str):
        self.host = host
        self.port = port
        self.sandbox_root = sandbox_root
        self.active_sessions = {}
        self._lock = threading.Lock()
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listening_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listening_socket.bind((self.host, self.port))

    def start(self) -> None:
        """Start the accept loop; this blocks until KeyboardInterrupt is received."""

        self.listening_socket.listen(1)
        print(f"[FTP Server listening on {self.host}:{self.port}]\n")

        try:
            while True:
                conn, addr = self.listening_socket.accept()
                print(f"[Client connected: {addr[0]}:{addr[1]}]\n")
                threading.Thread(
                    target=self._handle_client,
                    args=(conn, addr),
                    daemon=True,
                    name=f"client-{addr[0]}:{addr[1]}"
                ).start()

        except KeyboardInterrupt:
            print("[Server shutting down...]\n")

        finally:
            self.listening_socket.close()
            print("[Server closed]\n")

    def _handle_client(self, conn: socket.socket, addr: tuple[str, int]) -> None:
        """
        Handle one client connection.
        Create the session and dispatcher, read commands in a loop, then close.
        """
        conn.settimeout(SESSION_TIMEOUT_SECONDS)
        session = ClientSession(conn, addr, self.sandbox_root)
        dispatcher = CommandDispatcher(session, fs_manager=None, rdt_engine=None)

        with self._lock:
            self.active_sessions[addr] = session
        self._log_sessions()

        session.send_reply(ReplyCode.SERVICE_READY.format())

        try:
            while True:
                raw_bytes = conn.recv(1024)
                if not raw_bytes:
                    break  # client closed the connection

                raw_line = deserialize_message(raw_bytes)

                print(f"[Received from {addr[0]}:{addr[1]}]\n{raw_line.strip()}\n")
                should_continue = dispatcher.dispatch(raw_line)
                if not should_continue:
                    break

        except socket.timeout:
            print(f"[Session timeout for client {addr[0]}:{addr[1]}]\n")
        except Exception as e:
            print(f"[Error handling client {addr[0]}:{addr[1]}]\n{e}\n")

        finally:
            with self._lock:
                self.active_sessions.pop(addr, None)
            conn.close()
            print(f"[Client disconnected: {addr[0]}:{addr[1]}]\n")
            self._log_sessions()

    def _log_sessions(self) -> None:
        """Print the active session table to the server console."""
        with self._lock:
            if not self.active_sessions:
                print("[SESSIONS] No active sessions.\n")
                return
            print(f"[SESSIONS] Active ({len(self.active_sessions)}):")
            for session_addr, sess in self.active_sessions.items():
                print(f"  {session_addr[0]}:{session_addr[1]} | {sess.auth_state.name} | {sess.cwd}")
            print()
