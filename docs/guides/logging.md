# Logging

Use Python's standard [`logging`](https://docs.python.org/3/library/logging.html)
module to record diagnostic messages in a marimo notebook. In the editor,
messages written to standard output or standard error appear both below the
cell and in the **Logs** panel.

To open **Logs**, expand the developer panel with `Cmd/Ctrl-J` and select the
**Logs** tab. See [Sidebar and developer panel](editor_features/panels.md) for
layout and visibility controls.

## Set up a notebook logger

Run this in one cell:

```python
import logging
import marimo as mo

logger = logging.getLogger("my_notebook")
logger.setLevel(logging.INFO)
logger.propagate = False

for _handler in logger.handlers[:]:
    logger.removeHandler(_handler)
    _handler.close()

_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
logger.addHandler(_handler)
```

This configures a dedicated logger without changing the root logger or other
libraries' logging configuration. Replacing its handlers prevents duplicate
messages when you rerun the setup cell. Setting `propagate = False` prevents
the root logger's handlers from also emitting these messages.

In another cell, log a message:

```python
logger.info("Starting analysis")
logger.debug("This message is filtered out at the INFO level")
```

`StreamHandler()` writes to standard error by default. The **STDOUT** and
**STDERR** labels in the Logs panel identify the stream, not the Python log
level: an `INFO` message sent to standard error is still labeled **STDERR**.
The formatter above includes the Python level in the message itself.

### Choose a log level

Change `logger.setLevel(logging.INFO)` in the setup cell to
`logger.setLevel(logging.DEBUG)` to include debug messages, or to
`logger.setLevel(logging.WARNING)` to show only warnings and more severe
messages. Python's levels, from least to most severe, are `DEBUG`, `INFO`,
`WARNING`, `ERROR`, and `CRITICAL`.

Filtering happens before messages reach marimo, so filtered messages appear
neither below the cell nor in the Logs panel. The Logs panel does not provide
a Python log-level filter.

## Keep logs without leaving console output below a cell

Call [`mo.output.clear_console()`][marimo.output.clear_console] after logging
in the same cell. This clears that cell's console output while preserving
the messages in the Logs panel:

```python
logger.info("Starting analysis")
result = sum(range(10))
logger.info("Analysis complete: %s", result)
mo.output.clear_console()

mo.md(f"The result is **{result}**.")
```

After the cell finishes, its visual output shows the result and its console
area is empty. The diagnostic messages remain available in **Logs**.

!!! note "Clearing is not disabling console output"

    Messages can appear below the cell while it runs, before the clear call.
    Later writes appear there again. The call clears all console output from
    the current cell, including `print()` output and standard error, not just
    messages from this logger. It does not clear other cells' consoles or the
    cell's visual output. If execution fails before the call, the console
    output is not cleared.

marimo does not provide a built-in logging handler that routes messages
exclusively to the Logs panel. Use `clear_console()` when you want to retain
diagnostics in Logs and leave a clean cell console after execution.

## Clear or hide the Logs panel

Use **Clear** in the Logs panel to clear its accumulated history. This is
separate from `mo.output.clear_console()`: clearing the panel does not clear
the console output below cells, and clearing a cell's console does not clear
the panel's history.

Toggle the developer panel with `Cmd/Ctrl-J` to hide or show it. Hiding the
panel changes its visibility; it does not stop logging or filter messages.
Panel visibility and clearing its history are editor controls, not Python
logging settings.

## Logging to a terminal or file

In edit mode (`marimo edit notebook.py`), marimo captures standard output and
standard error for the notebook UI. These are different from the terminal
where you started marimo.

When serving an app with `marimo run notebook.py`, console output goes to the
terminal by default. The `--redirect-console-to-browser` option redirects it
to the browser instead. Running a notebook as a script with
`python notebook.py` also uses the process's standard output and standard
error.

To write this logger's messages to a file instead of the notebook console,
replace `logging.StreamHandler()` in the setup cell with
`logging.FileHandler("notebook.log", encoding="utf-8")`. File logging does not
populate the Logs panel; the panel displays captured console output.

For displaying console text as part of your notebook's visual output, see
[Console outputs](outputs.md#console-outputs).
