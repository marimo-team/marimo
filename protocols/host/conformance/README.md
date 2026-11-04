# Host protocol conformance tests

This suite checks hosts through the [host protocol](../spec.md) HTTP and SSE
interfaces. Offline tests validate the schema, shared fixtures, and
checker behavior. The input fixtures illustrate answering, cancellation,
output ordering, and reconnecting while a prompt is pending.

To check a running host, start it in a disposable workspace, using `marimo edit`
for marimo, then run the suite from the repository root.

```sh
uv run --locked --project protocols/host/conformance \
  pytest protocols/host/conformance --record /path/to/hosts-v1/host.json
```

The caller starts and stops the host, while operation tests create scratch
notebooks and clean up their own resources. Omitting `--record` runs only the
offline tests, which also run in CI through `make host-protocol-check`.

Scratch checks inspect the created notebook for `notebook.delete` permission
so they can clean it up afterward. When the notebook withholds that permission,
the suite skips the remaining scratch checks and reports its ID for manual
cleanup in the disposable workspace.

- `--slow` includes idle ping checks.
- `--host-timeout 30` allows longer waits for a host's responses and events.
- `--require-operation runtime.run` fails if that capability is missing. Repeat
  this option to require more operations. Tests for unavailable operations
  otherwise skip.

The live tests cover discovery records, authentication, snapshots, filtering,
resumption, document hashes, and selected notebook and runtime operations.
They do not yet cover input, opening an editor, answering host decisions, or
unsupported operation responses. Retention expiry, external store changes,
shutdown, and transport failures also need implementation tests. WebSocket
transport is outside this contract.

Experimental features have separate conformance tests. Check the stable
contract and all experimental fixtures together with this command.

```sh
uv run --locked --project protocols/host/conformance \
  pytest -c protocols/host/conformance/pyproject.toml \
  protocols/host/conformance protocols/host/experimental
```

The base probes continue to ignore experimental events. Each feature's suite
validates its payloads against the composed contract.
