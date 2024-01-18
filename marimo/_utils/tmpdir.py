# Copyright 2024 Marimo. All rights reserved.
import os
import sys
import tempfile


def _convert_to_long_pathname(filename: str) -> str:
    return filename


if sys.platform == "win32":
    # Adapted from IPython.core.compilerop
    #
    # https://github.com/ipython/ipykernel/blob/93a63fb7b8752899ed95118fa35e56f74eedd0c6/ipykernel/compiler.py  # noqa: E501
    try:
        import ctypes
        from ctypes.wintypes import DWORD, LPCWSTR, LPWSTR, MAX_PATH

        _GetLongPathName = ctypes.windll.kernel32.GetLongPathNameW
        _GetLongPathName.argtypes = [LPCWSTR, LPWSTR, DWORD]
        _GetLongPathName.restype = DWORD

        def _win_convert_to_long_pathname(filename: str) -> str:
            buf = ctypes.create_unicode_buffer(MAX_PATH)
            rv = _GetLongPathName(filename, buf, MAX_PATH)
            if rv != 0 and rv <= MAX_PATH:
                filename = buf.value
            return filename

        # test that it works so if there are any issues we fail just once here
        _win_convert_to_long_pathname(__file__)
    except Exception:
        pass
    else:
        _convert_to_long_pathname = _win_convert_to_long_pathname


def get_tmpdir() -> str:
    return os.path.join(
        _convert_to_long_pathname(tempfile.gettempdir()),
        "marimo_" + str(os.getpid()),
    )
