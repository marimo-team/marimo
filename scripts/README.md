Development utilities. Should be run from the root directory of the project.

## Host inspection

`host_events.py` follows the event stream of a local marimo edit server, or
prints a snapshot of its current state. The server must run before you start
the script. Run `uv run scripts/host_events.py --help` for usage.
