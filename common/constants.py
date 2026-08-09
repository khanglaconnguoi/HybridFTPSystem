# common/constants.py

CHUNK_SIZE   = 1024   # bytes/gói payload
WINDOW_SIZE  = 8      # số gói được gửi trước khi chờ ACK
TIMEOUT      = 0.5    # giây — timeout 1 gói
MAX_RETRY    = 10     # số lần thử lại tối đa mỗi gói
