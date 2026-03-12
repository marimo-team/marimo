import re
from pathlib import Path
from typing import Any


def on_page_markdown(markdown: str, page: Any = None, **kwargs: Any) -> str:
    del kwargs
    static_dir = Path("docs/")
    if not static_dir.exists():
        return markdown

    # Find all src="/" patterns
    pattern = r'src="(/[^"]+)"'
    matches = re.finditer(pattern, markdown)

    for match in matches:
        src_path = match.group(1)
        # Remove leading slash and check if file exists in _static
        relative_path = src_path.lstrip("/")
        full_path = static_dir / relative_path

        if not full_path.exists():
            print(f"\u26a0\ufe0f  Warning: Static asset not found: {src_path}")
            print(f"   Expected at: {full_path}")

    # Auto-generate meta description from page content if not set
    if page and not page.meta.get("description"):
        description = _extract_description(markdown)
        if description:
            page.meta["description"] = description

    return markdown


def _extract_description(markdown: str) -> str:
    """Extract a meta description from the first meaningful paragraph."""
    # Strip HTML blocks (style, script, div, p, table, video, etc.) before parsing
    cleaned = re.sub(
        r"<(style|script|video|table|figure)[^>]*>.*?</\1>",
        "",
        markdown,
        flags=re.DOTALL | re.IGNORECASE,
    )

    lines = cleaned.split("\n")
    paragraph_lines: list[str] = []
    in_frontmatter = False
    past_frontmatter = False
    in_code_block = False
    in_admonition = False

    for line in lines:
        stripped = line.strip()

        # Skip YAML frontmatter
        if stripped == "---":
            if not past_frontmatter:
                in_frontmatter = not in_frontmatter
                if not in_frontmatter:
                    past_frontmatter = True
                continue
        if in_frontmatter:
            continue

        # Skip code blocks
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        # Skip headings
        if stripped.startswith("#"):
            # If we already collected paragraph text, stop
            if paragraph_lines:
                break
            continue

        # Skip HTML tags, admonitions, and directives
        if stripped.startswith("<") or stripped.startswith("///"):
            if stripped.startswith("///"):
                in_admonition = not in_admonition
            if paragraph_lines:
                break
            continue
        if in_admonition:
            continue

        # Skip empty lines
        if not stripped:
            if paragraph_lines:
                break
            continue

        # Skip markdown images and links-only lines
        if re.match(r"^!?\[.*\]\(.*\)$", stripped):
            continue

        # Skip lines starting with ??? or !!! (admonition shorthand)
        if stripped.startswith("???") or stripped.startswith("!!!"):
            if paragraph_lines:
                break
            continue

        # Skip lines that are just formatting (bold/italic markers, list items)
        if re.match(r"^[*_\-|]", stripped) and not re.match(
            r"^[*_]{1,2}\w", stripped
        ):
            if paragraph_lines:
                break
            continue

        paragraph_lines.append(stripped)

    if not paragraph_lines:
        return ""

    text = " ".join(paragraph_lines)

    # Remove markdown formatting
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # [text](url) -> text
    text = re.sub(r"`([^`]+)`", r"\1", text)  # `code` -> code
    text = re.sub(r"[*_]{1,2}([^*_]+)[*_]{1,2}", r"\1", text)  # bold/italic
    text = re.sub(r"\s+", " ", text).strip()  # normalize whitespace

    # Truncate to ~155 characters at a word boundary
    max_length = 155
    if len(text) > max_length:
        text = text[:max_length].rsplit(" ", 1)[0] + "..."

    return text
