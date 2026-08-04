from enum import Enum
from typing import Optional


class ReplyCode(Enum):
    # 1xx Positive Preliminary
    RESTART_MARKER = (110, "MARK {yyyy} = {mmmm}")
    SERVICE_READY_IN = (120, "Service ready in {nnn} minutes.")
    DATA_CONN_OPEN = (125, "Data connection already open; transfer starting.")
    OPENING_DATA_CONN = (150, "File status okay, opening data connection.")

    # 2xx Positive Completion
    COMMAND_OK = (200, "Command okay.")
    SUPERFLUOUS_COMMAND = (202, "Command not implemented, superfluous at this site.")
    SYSTEM_STATUS = (211, "System status, or system help reply.")
    DIRECTORY_STATUS = (212, "Directory status.")
    FILE_STATUS = (213, "File status.")
    HELP_MESSAGE = (214, "Help message.")
    NAME_SYSTEM_TYPE = (215, "{system_type} system type.")
    SERVICE_READY = (220, "Service ready for new user.")
    GOODBYE = (221, "Goodbye.")
    DATA_CONN_OPEN_NO_TRANSFER = (225, "Data connection open; no transfer in progress.")
    TRANSFER_COMPLETE = (226, "Closing data connection. Transfer complete.")
    ENTERING_PASSIVE = (227, "Entering Passive Mode ({h1},{h2},{h3},{h4},{p1},{p2}).")
    LOGIN_SUCCESS = (230, "User logged in, proceed.")
    FILE_ACTION_OK = (250, "Requested file action okay, completed.")
    PATH_CREATED = (257, '"{path}" is the current directory.')

    # 3xx Positive Intermediate
    NEED_PASSWORD = (331, "User name okay, need password.")
    NEED_ACCOUNT = (332, "Need account for login.")
    PENDING_RNTO = (350, "Requested file action pending further information.")

    # 4xx Transient Negative
    SERVICE_UNAVAILABLE = (421, "Service not available, closing control connection.")
    CANT_OPEN_DATA_CONN = (425, "Cannot open data connection.")
    TRANSFER_ABORTED = (426, "Connection closed; transfer aborted.")
    FILE_BUSY = (450, "Requested file action not taken. File unavailable.")
    LOCAL_ERROR = (451, "Requested action aborted: local error in processing.")
    INSUFFICIENT_STORAGE = (452, "Requested action not taken. Insufficient storage space in system.")

    # 5xx Permanent Negative
    SYNTAX_ERROR = (500, "Syntax error, command unrecognized.")
    SYNTAX_ERROR_PARAM = (501, "Syntax error in parameters or arguments.")
    NOT_IMPLEMENTED = (502, "Command not implemented.")
    BAD_SEQUENCE = (503, "Bad sequence of commands.")
    PARAM_NOT_IMPLEMENTED = (504, "Command not implemented for that parameter.")
    NOT_LOGGED_IN = (530, "Not logged in.")
    NEED_ACCOUNT_FOR_STORING = (532, "Need account for storing files.")
    FILE_UNAVAILABLE = (550, "File unavailable.")
    PAGE_TYPE_UNKNOWN = (551, "Requested action aborted: page type unknown.")
    EXCEEDED_STORAGE = (552, "Requested file action aborted. Exceeded storage allocation.")
    FILE_NAME_NOT_ALLOWED = (553, "Requested action not taken. File name not allowed.")

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message

    def format(self, custom_msg: Optional[str] = None, **kwargs) -> str:
        """Return a standard FTP reply string: \"NNN Message\\r\\n\"."""
        msg = custom_msg if custom_msg is not None else self.message
        if kwargs:
            msg = msg.format(**kwargs)
        return f"{self.code} {msg}\r\n"

