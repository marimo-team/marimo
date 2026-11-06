# Host protocol conformance tests

This suite validates the [host protocol](../spec.md) schema and fixtures and
checks host behavior through HTTP and SSE. Run `make host-protocol-check` from
the repository root for the offline checks, including experimental features.

To check a running host, start it in a disposable workspace and pass its
discovery record. The suite creates and modifies notebooks during these tests.

```sh
uv run --locked --project protocols/host/conformance \
  pytest protocols/host/conformance --record /path/to/hosts-v1/host.json
```

The caller manages the host's lifecycle. Replace `--record` and its path with
`--help` to see the runner's options.
