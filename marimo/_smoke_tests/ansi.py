# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.8.3"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __():
    print(
        "".join(
            "\x1b[{}m{}\n\x1b[0m".format(31 + i, "Hello, World!") for i in range(8)
        )
    )
    return


@app.cell
def __():
    txt = "\n\n\x1B[1;33;40m 33;40  \x1B[1;33;41m 33;41  \x1B[1;33;42m 33;42  \x1B[1;33;43m 33;43  \x1B[1;33;44m 33;44  \x1B[1;33;45m 33;45  \x1B[1;33;46m 33;46  \x1B[1m\x1B[0\n\n\x1B[1;33;42m >> Tests OK\n\n"

    print(txt)
    return txt,


@app.cell
def __():
    import sys

    print("Hello world", file=sys.stderr)
    return sys,


@app.cell
def __():
    # No ANSI conversion when not stdout or stderr
    "".join("\x1b[{}m{}\n\x1b[0m".format(31 + i, "Hello, World!") for i in range(8))
    return


@app.cell
def __():
    # Colors input()
    input("\x1b[34mPress Enter to continue\x1b[0m")
    return


@app.cell
def __():
    import logging

    # ANSI escape codes for colors
    class AnsiColorFormatter(logging.Formatter):
        COLOR_CODES = {
            'DEBUG': '\033[94m',    # Blue
            'INFO': '\033[92m',     # Green
            'WARNING': '\033[93m',  # Yellow
            'ERROR': '\033[91m',    # Red
            'CRITICAL': '\033[95m', # Magenta
        }
        RESET_CODE = '\033[0m'

        def format(self, record):
            color = self.COLOR_CODES.get(record.levelname, self.RESET_CODE)
            return f"{color}{super().format(record)}{self.RESET_CODE}"

    # Configure the logging
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Add a new handler
    handler = logging.StreamHandler()
    formatter = AnsiColorFormatter('%(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Example log messages
    logging.error(f"\033[1;32mDirectory created at /path/to/dir\033[0m")
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")
    return AnsiColorFormatter, formatter, handler, logger, logging


if __name__ == "__main__":
    app.run()
