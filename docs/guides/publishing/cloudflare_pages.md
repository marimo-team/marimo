# Publish to Cloudflare Pages

You can publish executable notebooks to [Cloudflare Pages](https://pages.cloudflare.com/)
for free, after exporting your notebook to a WebAssembly notebook.

## Export to WASM-powered HTML

Export your notebook to a self-contained HTML file that runs using [WebAssembly](../wasm.md):

/// tab | Export as a readonly app

```bash
marimo export html-wasm notebook.py -o output_dir --mode run
```

///

/// tab | Export as an editable notebook

```bash
marimo export html-wasm notebook.py -o output_dir --mode edit
```

///

See our [exporting guide](../exporting.md#export-to-wasm-powered-html) for
the full documentation.

## Publish to Cloudflare Pages using GitHub

Create a new GitHub repository by visiting [repo.new](https://repo.new/) . After creating a new repository, go to your newly created project directory to prepare and push your local application to GitHub by running the following commands in your terminal:

```
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
Build command (optional)	exit 0
Build output directory	    /
```

4. Save and Deploy

## Publish Manually

To deploy your site to Pages:

1. Create zip of the folder "output_dir"
2. Log in to the Cloudflare [Dashboard](https://dash.cloudflare.com) and select your account.
3. In Account Home, select Workers & Pages > Create application > Pages > Upload asset.
4. Enter a project name then click Upload and select output_dir.zip .
5. Save and Deploy