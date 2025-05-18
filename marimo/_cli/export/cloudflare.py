# Copyright 2025 Marimo. All rights reserved.
from pathlib import Path

from marimo._cli.print import bold, echo, green
from marimo._server.print import _utf8


def create_cloudflare_files(title: str, out_dir: Path) -> None:
    echo("\n" + _utf8("☁️☁️☁️☁️☁️☁️") + "\n")

    parent_dir = out_dir.parent
    index_js = parent_dir / "index.js"
    wrangler_jsonc = parent_dir / "wrangler.jsonc"
    created_files = False

    if index_js.exists():
        echo(
            f"Cloudflare {index_js.name} already exists at {green(str(index_js.absolute()))}. Skipping..."
        )
    else:
        created_files = True
        # Create index.js
        index_js.write_text(
            """
export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname.startsWith("/health")) {
      return new Response(JSON.stringify({ made: "with marimo" }), {
        headers: { "Content-Type": "application/json" },
      });
    }

    return env.ASSETS.fetch(request);
  },
};""".strip()
        )

    if wrangler_jsonc.exists():
        echo(
            f"Cloudflare {wrangler_jsonc.name} already exists at {green(str(wrangler_jsonc.absolute()))}. Skipping..."
        )
    else:
        created_files = True
        # Create wrangler.jsonc
        wrangler_jsonc.write_text(
            f"""
{{
  "name": "{title}",
  "main": "{index_js.name}",
  "compatibility_date": "2025-01-01",
  "assets": {{
    "directory": "./{out_dir.relative_to(parent_dir)}",
    "binding": "ASSETS"
  }}
}}""".strip()
        )

    cwd = ""
    if parent_dir != Path.cwd() and str(parent_dir) != ".":
        cwd = f" --cwd {parent_dir}"

    if created_files:
        echo(
            f"Cloudflare configuration files created at {green(str(parent_dir.absolute()))}."
        )

    echo(
        f"""
To run locally, run:

    {bold("npx wrangler dev" + cwd)}

To deploy to Cloudflare Pages, run:

    {bold("npx wrangler deploy" + cwd)}
"""
    )
    echo(_utf8("☁️☁️☁️☁️☁️☁️"))
