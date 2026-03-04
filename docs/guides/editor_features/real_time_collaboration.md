# Real-time collaboration

!!! warning "Experimental"

    Real-time collaboration is an experimental feature and may change in future releases.

marimo supports real-time collaborative editing, allowing multiple users to work on the same notebook simultaneously. Code edits, cursor positions, and selections are synced across all connected browser sessions using [Loro CRDT](https://loro.dev/).

## Enabling RTC

Add the following to your `marimo.toml` or notebook config:

```toml
[experimental]
rtc_v2 = true
```

Or set it in the UI via **Settings → Experimental → Real-time collaboration**.

Then start marimo in edit mode as usual — any additional browser sessions that open the same notebook will automatically sync.

## What syncs

- **Cell code edits** — changes appear in real time across all sessions
- **Cursor positions and selections** — remote cursors are shown with usernames and colors
- **Cell language type** — switching between Python and SQL is synced

## Limitations

- **Edit mode only** — RTC is not available in app/run mode
- **Not available in WASM** — browser-only marimo (e.g., marimo playground) does not support RTC
- **Code sync only** — cell outputs, variables, and runtime state are _not_ synced; each session has its own kernel
