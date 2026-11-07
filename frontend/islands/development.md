# Marimo Islands

marimo Islands embed notebook cell outputs and code in an existing page. The host controls the page layout and theme.

## Theme

Islands use one theme per page. Theme resolution checks these sources in order:

1. The VS Code theme, when present.
2. Theme markers on `body`, then `html`: `dark`, `dark-mode`, or `dark-theme` classes, their light equivalents, and `data-theme` or `data-mode` attributes.
3. The computed `color-scheme`, then nontransparent background colors.
4. Light mode.

Changes to host theme attributes, inline styles, and system color preferences update outputs and widgets automatically.
The system preference selects the theme only when the host supports both color schemes.

## Development

**Quick start - Run the demo**

```bash
pnpm dev:islands
# Using a prebuilt marimo wheel
VITE_WASM_MARIMO_PREBUILT_WHEEL=true pnpm dev:islands
```

This will:

- Auto-generate the demo HTML from `generate.py`
- Start Vite dev server with HMR
- Watch `generate.py` for changes and auto-reload

**Update the demo islands**

Just edit `islands/generate.py`, save, and the browser will automatically reload with your changes.

**Generate production HTML**

```bash
# Generate with CDN links (default - for deployment)
uv run ./islands/generate.py > islands/__demo__/index.html

# Generate for local production build testing
MODE=local uv run ./islands/generate.py > islands/__demo__/index.html

# Generate for Vite dev server (auto-done by pnpm dev:islands)
MODE=dev uv run ./islands/generate.py > islands/__demo__/index.html
```

## Build for Production

```bash
# Build the islands bundle
pnpm build:islands

# Output:
# - frontend/islands/dist/main.js
# - frontend/islands/dist/style.css
```
