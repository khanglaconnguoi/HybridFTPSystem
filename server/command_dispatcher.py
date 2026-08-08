from common.reply_codes import ReplyCode
from server.session import ClientSession
from server.handlers.fs_handler import FsHandler


class CommandDispatcher:
    """
    Receives raw command strings from the client, parses them,
    and routes them to the matching Module A / B / C handler.
    """

    session: ClientSession
    _fs: FsHandler  # FsHandler / FSManager provided by Module C
    _rdt: object  # RdtEngine provided by Module B
    _handlers: dict  # { "USER": callable, "RETR": callable, ... }

    def __init__(
        self, session: ClientSession, fs_manager: object = None, rdt_engine: object = None
    ):
        self.session = session
        self._fs = fs_manager if fs_manager is not None else FsHandler(session=session, root_dir=session.sandbox_root)
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
            "CWD": self._handle_cwd,
            "CDUP": self._handle_cdup,
            "MKD": self._handle_mkd,
            "RMD": self._handle_rmd,
            "LIST": self._handle_list,
            "NLST": self._handle_nlst,
            "SIZE": self._handle_size,
            "MDTM": self._handle_mdtm,
            "STOU": self._handle_stou,
            "APPE": self._handle_appe,
            "DELE": self._handle_dele,
            "RNFR": self._handle_rnfr,
            "RNTO": self._handle_rnto,
            "HASH": self._handle_hash,
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
    def _handle_stat(self, arg: str) -> bool: return self._not_implemented(arg)
    def _handle_help(self, arg: str) -> bool: return self._not_implemented(arg)

    # ------------------------------------------------------------------
    # Module C Handlers (File System & Directory Management)
    # ------------------------------------------------------------------
    def _handle_pwd(self, arg: str) -> bool:
        ok, reply = self._fs.handle_pwd(arg)
        self.session.send_reply(reply)
        return True

    def _handle_cwd(self, arg: str) -> bool:
        ok, reply = self._fs.handle_cwd(arg)
        self.session.send_reply(reply)
        return True

    def _handle_cdup(self, arg: str) -> bool:
        ok, reply = self._fs.handle_cdup(arg)
        self.session.send_reply(reply)
        return True

    def _handle_mkd(self, arg: str) -> bool:
        ok, reply = self._fs.handle_mkd(arg)
        self.session.send_reply(reply)
        return True

    def _handle_rmd(self, arg: str) -> bool:
        ok, reply = self._fs.handle_rmd(arg)
        self.session.send_reply(reply)
        return True

    def _handle_list(self, arg: str) -> bool:
        ok, reply = self._fs.handle_list(arg)
        self.session.send_reply(reply)
        return True

    def _handle_nlst(self, arg: str) -> bool:
        ok, reply = self._fs.handle_nlst(arg)
        self.session.send_reply(reply)
        return True

    def _handle_size(self, arg: str) -> bool:
        ok, reply = self._fs.handle_size(arg)
        self.session.send_reply(reply)
        return True

    def _handle_mdtm(self, arg: str) -> bool:
        ok, reply = self._fs.handle_mdtm(arg)
        self.session.send_reply(reply)
        return True

    def _handle_stou(self, arg: str) -> bool:
        ok, reply = self._fs.handle_stou(arg)
        self.session.send_reply(reply)
        return True

    def _handle_appe(self, arg: str) -> bool:
        res = self._fs.handle_appe(arg)
        reply = res[1] if isinstance(res, tuple) and len(res) >= 2 else str(res)
        self.session.send_reply(reply)
        return True

    def _handle_dele(self, arg: str) -> bool:
        ok, reply = self._fs.handle_dele(arg)
        self.session.send_reply(reply)
        return True

    def _handle_rnfr(self, arg: str) -> bool:
        res = self._fs.handle_rnfr(arg)
        if isinstance(res, tuple) and len(res) >= 2:
            ok, reply = res[0], res[1]
            if len(res) >= 3:
                self.session.rename_pending = res[2]
        else:
            reply = str(res)
        self.session.send_reply(reply)
        return True

    def _handle_rnto(self, arg: str) -> bool:
        ok, reply = self._fs.handle_rnto(arg)
        self.session.send_reply(reply)
        self.session.rename_pending = None
        return True

    def _handle_hash(self, arg: str) -> bool:
        parts = arg.split(" ", 1)
        path = parts[0] if parts else ""
        algo = parts[1] if len(parts) > 1 else "sha256"
        ok, reply = self._fs.handle_hash(path, algo)
        self.session.send_reply(reply)
        return True
