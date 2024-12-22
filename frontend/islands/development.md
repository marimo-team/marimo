# Marimo Islands

marimo islands are a way to render HTML "islands" each with static outputs and code. This differs from the normal "app mode" in the sense that there is no top-level app. In "island mode", we do not have access to the HTML of the parent page.

## Development

**Islands demo page**

```bash
pnpm dev:islands
```

**Generate an HTML page with islands**

```bash
# Generate
uv run ./islands/generate.py > islands/__demo__/index.html
# Run the Vite server
pnpm dev:islands
```
