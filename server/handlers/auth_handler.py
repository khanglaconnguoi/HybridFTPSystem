import json
import os

from common.reply_codes import ReplyCode
from server.session import AuthState, ClientSession

REGISTERED_USERS_FILE = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), "..", "internal_data", "registered_users.json"
    )
)


def _load_accounts() -> dict:
    os.makedirs(os.path.dirname(REGISTERED_USERS_FILE), exist_ok=True)
    if not os.path.exists(REGISTERED_USERS_FILE):
        default_accounts = {"admin": "1234"}
        with open(REGISTERED_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_accounts, f, indent=4)
        return default_accounts

    with open(REGISTERED_USERS_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            if isinstance(data, list):
                return {
                    item["username"]: item["password"]
                    for item in data
                    if isinstance(item, dict) and "username" in item and "password" in item
                }
            elif isinstance(data, dict):
                return data
            return {}
        except json.JSONDecodeError:
            return {}


class AuthHandler:
    """Handles commands related to authentication and session management."""

    def __init__(self, session: ClientSession):
        self.session = session

    def handle_user(self, username: str) -> tuple[bool, str]:
        if not username:
            return True, ReplyCode.SYNTAX_ERROR_PARAM.format("Username required.")

        username = username.strip()
        accounts = _load_accounts()
        if username not in accounts:
            self.session.auth_state = AuthState.ANONYMOUS
            self.session.username = None
            return True, ReplyCode.NOT_LOGGED_IN.format("Invalid username.")

        self.session.username = username
        self.session.auth_state = AuthState.USER_OK
        return True, ReplyCode.NEED_PASSWORD.format()

    def handle_pass(self, password: str) -> tuple[bool, str]:
        if self.session.auth_state != AuthState.USER_OK:
            return True, ReplyCode.BAD_SEQUENCE.format("Send USER first.")

        accounts = _load_accounts()
        stored = accounts.get(self.session.username)
        if stored and stored == password.strip():
            self.session.auth_state = AuthState.LOGGED_IN
            return True, ReplyCode.LOGIN_SUCCESS.format()
        else:
            self.session.auth_state = AuthState.ANONYMOUS
            self.session.username = None
            return True, ReplyCode.NOT_LOGGED_IN.format("Login incorrect.")

    def handle_quit(self, _arg: str) -> tuple[bool, str]:
        # Return False to close the connection, along with the goodbye message
        return False, ReplyCode.GOODBYE.format()

    def handle_noop(self, _arg: str) -> tuple[bool, str]:
        return True, ReplyCode.COMMAND_OK.format("NOOP okay.")

    def handle_stat(self, _arg: str) -> tuple[bool, str]:
        info = (
            f"211-FTP server status:\r\n"
            f" Connected: {self.session.addr[0]}\r\n"
            f" User: {self.session.username}\r\n"
            f" CWD: {self.session.cwd}\r\n"
            f" Type: {self.session.transfer_type}\r\n"
            f"211 End of status."
        )

        return True, info

    def handle_help(self, command: str) -> tuple[bool, str]:
        return True, ReplyCode.HELP_MESSAGE.format(
            "Supported: USER PASS QUIT NOOP PWD STAT HELP CWD CDUP MKD RMD LIST NLST SIZE MDTM STOU APPE DELE RNFR RNTO HASH"
        )
