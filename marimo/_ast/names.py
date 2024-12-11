import hashlib

DEFAULT_CELL_NAME = "__"


def is_default_cell_name(name: str) -> bool:
    return name.startswith("__") and (name == "__" or len(name) == 6)


def default_cell_name_from_code(code: str) -> str:
    return (
        f"{DEFAULT_CELL_NAME}{hashlib.sha256(code.encode()).hexdigest()[:4]}"
    )
