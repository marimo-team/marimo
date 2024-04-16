import random

import pytest


@pytest.fixture
def py_modname() -> str:
    filename_chars = "abcdefghijklmopqrstuvwxyz"
    return "".join(random.sample(filename_chars, 20))


