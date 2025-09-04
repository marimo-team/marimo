import msgspec
import starlette.responses

from marimo._messaging.msgspec_encoder import encode_json_bytes


class StructResponse(starlette.responses.Response):
    media_type = "application/json"

    def __init__(self, struct: msgspec.Struct) -> None:
        super().__init__(content=encode_json_bytes(struct))
