from pathlib import Path

from marimo._cli.print import bold, echo, green
from marimo._server.print import _utf8


def create_cloudflare_files(title: str, out_dir: Path) -> None:
    parent_dir = out_dir.parent
    index_js = parent_dir / "index.js"
    wrangler_jsonc = parent_dir / "wrangler.jsonc"

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

    echo(
        f"""
{_utf8("☁️☁️☁️☁️☁️☁️")}
Cloudflare configuration files created at {green(str(parent_dir.absolute()))}.

To run locally, run:

    {bold("npx wrangler dev" + cwd)}

To deploy to Cloudflare Pages, run:

    {bold("npx wrangler deploy" + cwd)}

{_utf8("☁️☁️☁️☁️☁️☁️")}
"""
    )
