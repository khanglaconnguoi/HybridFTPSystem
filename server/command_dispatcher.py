from common.reply_codes import ReplyCode
from server.session import ClientSession


class CommandDispatcher:
    """
    Receives raw command strings from the client, parses them,
    and routes them to the matching Module A / B / C handler.
    """

    session: ClientSession
    _fs: object  # FsManager provided by Module C
    _rdt: object  # RdtEngine provided by Module B
    _handlers: dict  # { "USER": callable, "RETR": callable, ... }

    def __init__(
        self, session: ClientSession, fs_manager: object, rdt_engine: object
    ):
        self.session = session
        self._fs = fs_manager
        self._rdt = rdt_engine

        # Routing table: command string -> handler method
        self._handlers = {
            # Module A commands
            "USER": self._handle_user,
            "PASS": self._handle_pass,
            "QUIT": self._handle_quit,
            "NOOP": self._handle_noop,
            "PWD": self._handle_pwd,
            "STAT": self._handle_stat,
            "HELP": self._handle_help,
            # Module B commands
            "TYPE": self._not_implemented,
            "MODE": self._not_implemented,
            "PORT": self._not_implemented,
            "PASV": self._not_implemented,
            "RETR": self._not_implemented,
            "STOR": self._not_implemented,
            "ABOR": self._not_implemented,
            # Module C commands
            "CWD": self._not_implemented,
            "CDUP": self._not_implemented,
            "MKD": self._not_implemented,
            "RMD": self._not_implemented,
            "LIST": self._not_implemented,
            "NLST": self._not_implemented,
            "SIZE": self._not_implemented,
            "MDTM": self._not_implemented,
            "STOU": self._not_implemented,
            "APPE": self._not_implemented,
            "DELE": self._not_implemented,
            "RNFR": self._not_implemented,
            "RNTO": self._not_implemented,
            "HASH": self._not_implemented,
        }

    def _not_implemented(self, raw_args: str) -> bool:
        """Default handler for unimplemented commands."""
        self.session.send_reply(ReplyCode.NOT_IMPLEMENTED.format())
        return True

    def dispatch(self, raw_line: str) -> bool:
        """
        Parse one raw FTP command line and call the matching handler.

        Returns:
            True to continue receiving commands.
            False to close the session (for example after QUIT).
        """
        raw_line = raw_line.strip()
        if not raw_line:
            return True

        parts = raw_line.split(" ", 1)

        cmd = parts[0].upper()
        raw_args = parts[1] if len(parts) > 1 else ""

        handler = self._handlers.get(cmd)
        if handler is None:
            self.session.send_reply(ReplyCode.SYNTAX_ERROR.format())
            return True

        return handler(raw_args)  # False = close session

    def _handle_user(self, arg: str) -> bool: return self._not_implemented(arg)
    def _handle_pass(self, arg: str) -> bool: return self._not_implemented(arg)
    def _handle_quit(self, arg: str) -> bool: return self._not_implemented(arg)
    def _handle_noop(self, arg: str) -> bool: return self._not_implemented(arg)
    def _handle_pwd(self, arg: str) -> bool: return self._not_implemented(arg)
    def _handle_stat(self, arg: str) -> bool: return self._not_implemented(arg)
    def _handle_help(self, arg: str) -> bool: return self._not_implemented(arg)
