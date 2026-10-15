# Host protocol conformance tests

Python tests for hosts implementing the [host protocol](../spec.md). The suite
uses HTTP and SSE and does not import marimo.

Start a host in a disposable workspace, then run this from the repository root:

```sh
uv run --locked --project protocols/host/conformance \
  pytest protocols/host/conformance --record /path/to/hosts-v1/host.json
```

The caller starts and stops the host. Operation tests create scratch notebooks
and clean up their own resources. Without `--record`, only offline schema,
fixture, and checker tests run; these also run in CI via `make host-protocol-check`.

Scratch checks require the created notebook to permit `notebook.delete`.
That permission is only known after creation. If it is unavailable, the suite
skips the remaining scratch checks and reports the notebook ID for manual
cleanup in the disposable workspace.

- `--slow` includes idle ping checks.
- `--host-timeout 30` allows longer waits for a host's responses and events.
- `--require-operation runtime.run` fails if that capability is missing. Repeat
  this option to require more operations; otherwise unavailable operations skip.

The suite covers discovery records, authentication, snapshots, filtering,
resumption, document hashes, and selected notebook and runtime operations.
It does not yet cover opening an editor, answering host decisions, or unsupported
operation responses. Retention expiry, external store changes, shutdown, and
transport failures also need implementation tests. WebSocket transport is outside
this contract.
