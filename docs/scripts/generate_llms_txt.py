"""Generate an `llms.txt` index from the built docs.

Reads structure and page titles from the mkdocs `nav`, and page content from
the per-page markdown emitted by `html_to_markdown.py` (an `index.md` written
beside every `index.html`), then writes a compact [llmstxt.org](https://llmstxt.org)
index: a title, a blurb, and one section per top-level nav group, each a bullet
list linking to the `.md` version of every page.

Run this after `html_to_markdown.py` so the `.md` files exist:

    python docs/scripts/generate_llms_txt.py \\
        --input-dir .vercel/output/static \\
        --base-url https://docs.marimo.io \\
        --output-index .vercel/output/static/llms.txt
"""

# /// script
# requires-python = ">=3.10"
# dependencies = ["mkdocs>=1.6.1"]
# ///

import argparse
import re
from pathlib import Path

# mkdocs' loader understands the custom tags (!ENV, !relative) in mkdocs.yml;
# a plain yaml.safe_load would choke on them. mkdocs is always installed here
# (this script only runs under `uv run --group docs`).
from mkdocs.utils import yaml_load


def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml_load(f)


# Cap each page's one-line description so the index stays a compact, scannable
# map; anything longer is truncated with an ellipsis (see extract_description).
MAX_DESCRIPTION_LEN = 100


class Leaf:
    """A single documentation page reachable from the nav."""

    def __init__(self, title: str | None, path: str):
        self.title = title
        self.path = path

    @property
    def is_external(self) -> bool:
        return self.path.startswith(("http://", "https://"))


def walk(entry: object) -> list[Leaf]:
    """Flatten a nav subtree into an ordered list of leaves."""
    leaves: list[Leaf] = []
    if isinstance(entry, str):
        leaves.append(Leaf(None, entry))
    elif isinstance(entry, dict):
        for title, value in entry.items():
            if isinstance(value, str):
                leaves.append(Leaf(title, value))
            elif isinstance(value, list):
                for sub in value:
                    leaves.extend(walk(sub))
    return leaves


def parse_nav(nav: list) -> tuple[list[Leaf], list[tuple[str, list[Leaf]]]]:
    """Split the top-level nav into a prelude and titled sections.

    Returns `(prelude, sections)` where `prelude` is the top-level pages that
    aren't grouped under a section, and `sections` is `(title, leaves)` pairs.
    """
    prelude: list[Leaf] = []
    sections: list[tuple[str, list[Leaf]]] = []
    for entry in nav:
        if isinstance(entry, str):
            prelude.append(Leaf(None, entry))
        elif isinstance(entry, dict):
            for title, value in entry.items():
                if isinstance(value, str):
                    prelude.append(Leaf(title, value))
                elif isinstance(value, list):
                    leaves = [leaf for sub in value for leaf in walk(sub)]
                    sections.append((title, leaves))
    return prelude, sections


def resolve(path: str, input_dir: Path, base_url: str) -> tuple[Path, str]:
    """Map a nav source path to its built `.md` file and public `.md` URL.

    mkdocs (with `use_directory_urls`) builds `foo/bar.md` to `foo/bar/index.html`
    and `foo/index.md` to `foo/index.html`; `html_to_markdown.py` writes an
    `index.md` beside each. We link to the pretty `.md` URL, e.g.
    `guides/reactivity.md` -> `<base>/guides/reactivity.md`.
    """
    rel = path.removesuffix(".md")
    if rel == "index" or rel.endswith("/index"):
        disk = input_dir / f"{rel}.md"
        route = "" if rel == "index" else rel[: -len("/index")]
    else:
        disk = input_dir / rel / "index.md"
        route = rel
    url = f"{base_url}/{route}.md" if route else f"{base_url}/index.md"
    return disk, url


def strip_markdown(text: str) -> str:
    """Reduce inline markdown to plain-ish text for a one-line description."""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)  # images
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)  # links -> text
    text = re.sub(r"[`*_]", "", text)  # emphasis / code marks
    text = text.replace("¶", "")  # stray pilcrows
    return re.sub(r"\s+", " ", text).strip()


def extract_h1(md: str) -> str | None:
    for line in md.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return strip_markdown(s[2:])
    return None


def extract_description(md: str) -> str:
    """First prose paragraph after the H1, collapsed to a single line.

    Skips fenced code blocks (e.g. mkdocstrings signatures), headings, and
    other block markers so the description is real summary prose.
    """
    para: list[str] = []
    in_fence = False
    for line in md.splitlines():
        s = line.strip()
        if s.startswith("```"):
            in_fence = not in_fence
            if para:
                break
            continue
        if in_fence:
            continue
        if not s:
            if para:
                break
            continue
        # Skip source comment, headings, block markers, and the mkdocstrings
        # "Bases: ..." line, until real summary prose starts.
        if s.startswith(("<!--", "#", "|", ">", "-", "*", "!", "[", "Bases:")):
            if para:
                break
            continue
        para.append(s)
    text = strip_markdown(" ".join(para))
    if len(text) > MAX_DESCRIPTION_LEN:
        cut = text[:MAX_DESCRIPTION_LEN]
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        text = f"{cut.rstrip()}…"
    return text


def bullet(leaf: Leaf, input_dir: Path, base_url: str) -> str | None:
    """Render one index bullet, or None if the page has no built markdown."""
    if leaf.is_external:
        title = leaf.title or leaf.path
        return f"- [{title}]({leaf.path})"

    disk, url = resolve(leaf.path, input_dir, base_url)
    if not disk.exists():
        print(
            f"  warning: no built markdown for nav entry {leaf.path!r}, skipping"
        )
        return None

    md = disk.read_text(encoding="utf-8")
    title = (
        leaf.title or extract_h1(md) or Path(leaf.path).stem.replace("_", " ")
    )
    description = extract_description(md)
    return (
        f"- [{title}]({url}): {description}"
        if description
        else f"- [{title}]({url})"
    )


def render_index(
    prelude: list[Leaf],
    sections: list[tuple[str, list[Leaf]]],
    input_dir: Path,
    base_url: str,
    site_name: str,
    site_description: str,
) -> str:
    lines = [f"# {site_name}"]
    if site_description:
        lines.append(f"> {site_description}")
    lines.append("")

    for leaf in prelude:
        line = bullet(leaf, input_dir, base_url)
        if line:
            lines.append(line)
    if prelude:
        lines.append("")

    for title, leaves in sections:
        rendered = [
            b
            for b in (bullet(leaf, input_dir, base_url) for leaf in leaves)
            if b
        ]
        if not rendered:
            continue
        lines.append(f"## {title}")
        lines.extend(rendered)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate an llms.txt index from the built docs"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Path to the built site directory (containing the generated .md files)",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="https://docs.marimo.io",
        help="Base URL for page links",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("mkdocs.yml"),
        help="Path to mkdocs.yml (for nav, site_name, site_description)",
    )
    parser.add_argument(
        "--output-index",
        type=Path,
        required=True,
        help="Where to write llms.txt",
    )
    args = parser.parse_args()

    input_dir: Path = args.input_dir
    base_url: str = args.base_url.rstrip("/")

    if not input_dir.exists():
        raise SystemExit(f"Error: input directory {input_dir} does not exist")
    if not args.config.exists():
        raise SystemExit(f"Error: config {args.config} does not exist")

    config = load_yaml(args.config)
    nav = config.get("nav")
    if not nav:
        raise SystemExit(f"Error: no `nav` found in {args.config}")

    prelude, sections = parse_nav(nav)

    index = render_index(
        prelude,
        sections,
        input_dir,
        base_url,
        site_name=config.get("site_name", "marimo"),
        site_description=config.get("site_description", ""),
    )
    args.output_index.parent.mkdir(parents=True, exist_ok=True)
    args.output_index.write_text(index, encoding="utf-8")
    n_index = index.count("\n- ")
    print(f"Wrote {args.output_index} ({n_index} links, {len(index)} bytes)")


if __name__ == "__main__":
    main()
