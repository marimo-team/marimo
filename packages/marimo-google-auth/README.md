# marimo-google-auth

Colab-style Google auth bridge for [marimo](https://marimo.io) notebooks.

## What this is

A small shim that registers a `google.colab.auth.authenticate_user()` API
inside a marimo notebook kernel. With it installed:

```python
from google.colab import auth
auth.authenticate_user()

from gdrive_fsspec import GoogleDriveFileSystem
fs = GoogleDriveFileSystem(token="browser")
fs.ls("/")
```

…just works, without the `pydata-google-auth` "open `http://localhost:8080`"
flow that breaks in any remote/sandboxed runtime.

## Why this exists

`pydata-google-auth` (used by `gdrive-fsspec`, `pandas-gbq`, and others)
contains an escape hatch:

> *If `from google.colab import auth` imports successfully, use it
> instead of the local-webserver OAuth flow.*

Real Colab provides this module. marimo, by default, does not. This
package fills the gap: `authenticate_user()` opens an OAuth round-trip
through marimo's stdin channel (a frontend bridge owned by marimo /
molab / your own deployment handles the actual OAuth in the
browser), then returns a `google.oauth2.credentials.Credentials`
object directly to `pydata-google-auth` callers. It also writes ADC
and scope sidecar files; `google.auth.default()` can use the ADC file
until the access token expires, but cannot refresh through
`google-auth` because the refresh token is intentionally fake.

## Integration contract for deployers

If you're deploying marimo (self-hosted, or building a hosted product
like molab), you can install this package in your sandbox kernels.
You're then responsible for handling the auth-request stdin mimetype
on the frontend side.

In short, your frontend needs to:
1. Recognize the `application/x-marimo-auth-request` mimetype on a
   stdin-channel `CellOutput`.
2. Drive an OAuth flow that produces an access token for the requested
   scopes (the *how* is up to you — browser popup, parent-frame token
   service, identity provider integration, etc.).
3. POST the JSON response envelope back via the existing
   `/api/kernel/stdin` route.

The protocol is intentionally generic; this package only owns the
kernel-side surface.

## Status

Pre-alpha.

## Layout

This package lives inside the [marimo monorepo](https://github.com/marimo-team/marimo)
at `packages/marimo-google-auth/`. It is published to PyPI as a
separate distribution (`pip install marimo-google-auth`), but is
versioned and released alongside the kernel/frontend protocol it
depends on so that protocol changes land atomically across both
sides.

For local development inside the marimo monorepo:

```bash
uv pip install --python /path/to/marimo/.venv/bin/python \
    -e packages/marimo-google-auth[test]
pytest packages/marimo-google-auth/tests
```
