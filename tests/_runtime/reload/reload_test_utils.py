import pathlib
import random
import textwrap
import time


def random_modname():
    filename_chars = "abcdefghijklmopqrstuvwxyz"
    return "".join(random.sample(filename_chars, 20))


def update_file(path: pathlib.Path, code: str) -> None:
    """
    Comment from
    https://github.com/ipython/ipython/blob/fe52b206ecd0e566fff935fea36d26e0903ec34b/IPython/extensions/tests/test_autoreload.py#L128

    Python's .pyc files record the timestamp of their compilation
    with a time resolution of one second.

    Therefore, we need to force a timestamp difference between .py
    and .pyc, without having the .py file be timestamped in the
    future, and without changing the timestamp of the .pyc file
    (because that is stored in the file).  The only reliable way
    to achieve this seems to be to sleep.
    """
    time.sleep(1.05)
    path.write_text(textwrap.dedent(code))
