import re
from typing import Union


def natural_sort(filename: str) -> list[Union[int, str]]:
    def convert(text: str) -> Union[int, str]:
        return int(text) if text.isdigit() else text.lower()

    def alphanum_key(key: str) -> list[Union[int, str]]:
        return [convert(c) for c in re.split("([0-9]+)", key)]

    return alphanum_key(filename)
