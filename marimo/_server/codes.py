from enum import IntEnum


class WebSocketCodes(IntEnum):
    ALREADY_CONNECTED = 1003
    NORMAL_CLOSE = 1000
    FORBIDDEN = 1008
    UNEXPECTED_ERROR = 1011
