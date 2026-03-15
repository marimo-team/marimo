# Session snapshots

Run notebooks and write their serialized session snapshots.

## Export from the command line

```bash
marimo export session notebook.py
```

By default, snapshots are written to:

```text
<notebook_dir>/__marimo__/session/<notebook_filename>.json
```

For example, exporting `notebook.py` writes:

```text
__marimo__/session/notebook.py.json
```

## Export a directory

`marimo export session` accepts one positional target: a notebook file or a directory.
To process multiple notebooks, pass a directory target.

Export every notebook in a directory:

```bash
marimo export session folder/
```

## Passing CLI args

Pass CLI args through to notebooks with `--`:

```bash
marimo export session notebook.py -- --foo 123
```

## Staleness and force overwrite

By default, marimo only rewrites session snapshots when they are stale (for example, when notebook code changes or PEP 723 script metadata changes).
Up-to-date snapshots are skipped.

To force rewriting all snapshots, even when they are up-to-date:

```bash
marimo export session folder/ --force-overwrite
```

## Error handling

If one notebook fails, marimo continues by default and exits non-zero after processing all targets.
Use `--no-continue-on-error` to stop at the first failure.

## Sandboxed execution

To execute in a sandboxed environment, pass `--sandbox`:

```bash
marimo export session notebook.py --sandbox
```
