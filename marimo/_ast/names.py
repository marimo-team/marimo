import hashlib

DEFAULT_CELL_NAME = "__"


def is_internal_cell_name(name: str) -> bool:
    return name.startswith(DEFAULT_CELL_NAME)


NUMBER_OF_HASH_CHARS = 6


def default_cell_name_from_code(code: str) -> str:
    return f"{DEFAULT_CELL_NAME}{hashlib.sha256(code.encode()).hexdigest()[:NUMBER_OF_HASH_CHARS]}"
