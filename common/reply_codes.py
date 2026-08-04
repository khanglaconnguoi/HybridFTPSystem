from enum import Enum
from typing import Optional


class ReplyCode(Enum):
    # 1xx Positive Preliminary
    DATA_CONN_OPEN = (125, "Data connection already open; transfer starting.")
    OPENING_DATA_CONN = (150, "File status okay, opening data connection.")

    # 2xx Positive Completion
    COMMAND_OK = (200, "Command okay.")
    SYSTEM_STATUS = (211, "System status, or system help reply.")
    SERVICE_READY = (220, "Service ready for new user.")
    GOODBYE = (221, "Goodbye.")
    TRANSFER_COMPLETE = (226, "Closing data connection. Transfer complete.")
    LOGIN_SUCCESS = (230, "User logged in, proceed.")
    FILE_ACTION_OK = (250, "Requested file action okay, completed.")
    PATH_CREATED = (257, '"{path}" is the current directory.')

    # 3xx Positive Intermediate
    NEED_PASSWORD = (331, "User name okay, need password.")
    PENDING_RNTO = (350, "Requested file action pending further information.")

    # 4xx Transient Negative
    SERVICE_UNAVAILABLE = (421, "Service not available, closing control connection.")
    CANT_OPEN_DATA_CONN = (425, "Cannot open data connection.")
    TRANSFER_ABORTED = (426, "Connection closed; transfer aborted.")
    FILE_BUSY = (450, "Requested file action not taken. File unavailable.")

    # 5xx Permanent Negative
    SYNTAX_ERROR = (500, "Syntax error, command unrecognized.")
    SYNTAX_ERROR_PARAM = (501, "Syntax error in parameters or arguments.")
    NOT_IMPLEMENTED = (502, "Command not implemented.")
    BAD_SEQUENCE = (503, "Bad sequence of commands.")
    NOT_LOGGED_IN = (530, "Not logged in.")
    FILE_UNAVAILABLE = (550, "File unavailable.")

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message

    def format(self, custom_msg: Optional[str] = None) -> str:
        """Return a standard FTP reply string: \"NNN Message\\r\\n\"."""
        msg = custom_msg if custom_msg is not None else self.message
        return f"{self.code} {msg}\r\n"
