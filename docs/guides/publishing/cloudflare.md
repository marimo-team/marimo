# Publish to Cloudflare

You can publish executable notebooks to [Cloudflare Workers](https://workers.cloudflare.com/)
for free, after exporting your notebook to a WebAssembly notebook.

## Export to WASM-powered HTML

Export your notebook to a self-contained HTML file that runs using [WebAssembly](../wasm.md) with the flag `--include-cloudflare`:

/// tab | Export as a readonly app

```bash
marimo export html-wasm notebook.py -o output_dir --mode run --include-cloudflare
```

///

/// tab | Export as an editable notebook

```bash
marimo export html-wasm notebook.py -o output_dir --mode edit --include-cloudflare
```

///

See our [exporting guide](../exporting.md#export-to-wasm-powered-html) for
the full documentation.

## Publish to a Cloudflare Worker

When you use the `--include-cloudflare` flag, marimo creates two additional files in the parent directory of your output directory:

- `index.js`: A simple Cloudflare Worker script that serves your static assets
- `wrangler.jsonc`: Configuration for Cloudflare's Wrangler CLI

To run locally, run:

```bash
npx wrangler dev
```

To deploy to Cloudflare, run:

```bash
npx wrangler deploy
```

/// admonition | Need authentication or custom endpoints?
    type: tip

You can modify the `index.js` to include authentication or custom endpoints. This allows you to:

- Add authentication logic to protect your notebook
- Create API endpoints that serve data from the same domain, avoiding CORS issues

///

## Publish to Cloudflare Pages using GitHub

As an alternative to Cloudflare Workers, you can publish to Cloudflare Pages. To get started, create a new GitHub repository by visiting [repo.new](https://repo.new/) . After creating a new repository, go to your newly created project directory to prepare and push your local application to GitHub by running the following commands in your terminal:

```bash
cd output_dir
git init
git remote add origin https://github.com/<your-gh-username>/<repository-name>
git add .
git commit -m "Initial commit"
git branch -M main
git push -u origin main

```

To deploy your site to Pages:

1. Log in to the Cloudflare [Dashboard](https://dash.cloudflare.com) and select your account.
2. In Account Home, select Workers & Pages > Create application > Pages > Connect to Git.
3. Select the new GitHub repository that you created and, in the Set up builds and deployments section, provide the following information:

```
Project name                output-dir
Production branch           main
Framework preset            None
Build command (optional) exit 0
Build output directory     /
```

4. Save and Deploy

## Publish to Cloudflare Pages Manually

To deploy your site to Pages:

1. Create zip of the folder "output_dir"
2. Log in to the Cloudflare [Dashboard](https://dash.cloudflare.com) and select your account.
3. In Account Home, select Workers & Pages > Create application > Pages > Upload asset.
4. Enter a project name then click Upload and select output_dir.zip .
5. Save and Deploy
