<style>
  td code {
    white-space: nowrap;
  }
</style>

::: mkdocs-click
    :module: marimo._cli.cli
    :command: main
    :prog_name: marimo
    :depth: 0
    :style: table

## Listen to notebook events

Use `marimo pair notebook list` to find a notebook's ID, then follow its host
event stream:

```bash
marimo pair notebook events <notebook-id> \
  --url http://localhost:2718 \
  --types runtime,execution
```

The command prints one JSON object per line, with `event`, `data`, and an `id`
cursor when the server supplies one. The initial snapshot ends with `ready`;
live changes follow. Heartbeat comments are omitted. Unknown event names and
payload fields are preserved, so the command also works with protocol extensions.

Add `--pretty` to indent each event's JSON across multiple lines, with a blank
line between events. The default remains one JSON object per line for scripts.

`--types` accepts comma-separated names. Whitespace around names is ignored;
empty entries are rejected. Omit the option to receive all event types.

Authentication comes from the private local host record. The command requires
a local edit server. Press **Ctrl-C** to stop. If the server disconnects, run
the command again to receive a fresh snapshot and continue listening.
