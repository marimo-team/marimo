# Marimo Islands

marimo islands are a way to render HTML "islands" each with static outputs and code. This differs from the normal "app mode" in the sense that there is no top-level app. In "island mode", we do not have access to the HTML of the parent page.

## Development

**Quick start - Run the demo**

```bash
pnpm dev:islands
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
