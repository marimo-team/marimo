---
description: Using marimo with git — what to ignore and when to commit `__marimo__` artifacts
---

# Version control

marimo writes a few generated files next to your notebooks. Most of them should
stay out of git; a few are optional when you want previews or social images in
the repo.

## Recommended `.gitignore`

Add:

```gitignore
**/__marimo__/
```

That ignores:

- `__marimo__/cache/` — disk cache for [`mo.persistent_cache`][marimo.persistent_cache]
- `__marimo__/session/` — session JSON used for static previews
- `__marimo__/assets/` — generated OpenGraph images and similar assets

## When to commit under `__marimo__`

Keep the directory ignored by default. Commit pieces only when something
downstream needs them in the repo:

- **Static previews** (GitHub / molab) — commit the notebook’s session JSON under
  `__marimo__/session/`. Generate it with
  `marimo export session notebook.py`. See
  [session snapshots](exporting/sessions.md) and
  [publishing on GitHub](publishing/github.md).
- **OpenGraph images** — commit
  `__marimo__/assets/<notebook_stem>/opengraph.png`.
  See [OpenGraph](publishing/opengraph.md).

Example that still drops cache but allows previews and assets:

```gitignore
**/__marimo__/cache/
# !**/__marimo__/session/
# !**/__marimo__/assets/
```

## Related

- [`mo.persistent_cache`][marimo.persistent_cache] (API notes also mention ignoring cache)
- [Exporting sessions](exporting/sessions.md)
