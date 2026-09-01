## CLI execution bridge

Use `marimo pair execute` as the execution bridge.

Selected target:

- Server: `{server_url}`
- Session: `{session_id}`
- Notebook key: `{notebook_key}`
- marimo version: `{version}`
- Token source: `{token_source}`

Use this resumable command for each Python body:

```bash
{execute_command}
```

Submit the required first command from the canonical guide by itself.
If context is compacted, run `marimo pair guide` again before you continue.
