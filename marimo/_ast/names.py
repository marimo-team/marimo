DEFAULT_CELL_NAME = "__"


def is_default_cell_name(name: str) -> bool:
    return name.startswith("__") and (name == "__" or name[2:].isdigit())
