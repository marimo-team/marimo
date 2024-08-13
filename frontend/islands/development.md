# Marimo Islands

marimo islands are a way to render HTML "islands" each with static outputs and code. This differs from the normal "app mode" int that there is no top-level app. In "island mode", we do not have access to the HTML of the parent page.

## Development

**Islands demo page**

```bash
pnpm dev:islands
```

**Generate an HTML page with islands**

```bash
# Generate
python3 ./islands/generate.py > islands/__demo__/index.html
# Run the Vite server
pnpm dev:islands
```

**ESM demo page**

```bash
# Build the esm package and watch for changes
pnpm preview:islands --watch
```

**Server the ESM files**

```bash
# in marimo/frontend
npx serve dist --cors
```

Visit <http://localhost:3000/main.js> to verify that the ESM files are being served correctly.

**Run the ESM demo page**

```bash
npx serve islands/__demo__/esm --cors -p 3009
```

Visit <http://localhost:3009> to see the ESM demo page.
