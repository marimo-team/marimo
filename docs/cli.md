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
Pretty output uses syntax colors in supported terminals. Piped output stays
plain. Set `NO_COLOR=1` to disable colors.

`--types` accepts comma-separated names. Whitespace around names is ignored;
empty entries are rejected. Omit the option to receive all event types.

Authentication comes from the private local host record. The command requires
a local edit server. Press **Ctrl-C** to stop. If the server disconnects, run
the command again to receive a fresh snapshot and continue listening.

## Read a snapshot

Read the host catalog as one JSON response:

```bash
marimo pair snapshot --url http://localhost:2718 --pretty
```

Read one notebook's current state and retained results:

```bash
marimo pair snapshot --url http://localhost:2718 \
  --notebook <notebook-id> --pretty
```

The response contains `cursor` and `events`. The events are current records in
dependency order, not a replay of old messages. Objects still present are
included even after their original events leave the replay history. Removed
objects, expired results, and custom occurrences are absent. There is no
`ready` event; its cursor is the top-level `cursor` field instead.

Use `--types runtime,execution` to filter records. The same local host
authentication and pretty-output color rules apply as for `notebook events`.
Snapshot reads exit after the response and do not create a client attachment.

The underlying HTTP routes are `GET /api/marimo/v1/snapshot` and
`GET /api/marimo/v1/notebooks/<notebook-id>/snapshot`. A client can pass the
returned cursor as `Last-Event-ID` to the matching event stream, keeping the
same filters. An expired cursor causes a reset and a new snapshot.
