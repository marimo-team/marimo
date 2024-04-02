# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.88"
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


if __name__ == "__main__":
    app.run()
