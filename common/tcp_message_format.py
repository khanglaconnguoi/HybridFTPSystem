def serialize_message(message: str) -> bytes:
    """Serialize an FTP command/reply as a CRLF-terminated line."""
    final_message = message
    if not message.endswith("\r\n"):
        final_message += "\r\n"
    return final_message.encode("utf-8")

def deserialize_message(data: bytes) -> str:
    """Deserialize a CRLF-terminated line into a string."""
    return data.rstrip(b"\r\n").decode("utf-8")
