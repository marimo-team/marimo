"""Convert mkdocs-built HTML pages to clean markdown for AI agent consumption.

Walks the build output directory, extracts article content from each page,
and writes a markdown version alongside each index.html.
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from markdownify import MarkdownConverter


class DocsMarkdownConverter(MarkdownConverter):
    """Custom markdownify converter for mkdocs-material HTML."""

    def __init__(self, base_url: str, page_path: str, **kwargs):
        self.base_url = base_url.rstrip("/")
        self.page_path = page_path
        super().__init__(**kwargs)

    def convert_pre(self, el: Tag, text: str, **kwargs) -> str:
        """Convert <pre> code blocks by stripping Pygments spans."""
        code_el = el.find("code")
        if code_el:
            # Extract raw text, stripping all Pygments <span> tags
            raw_code = code_el.get_text()
            # Try to detect language from class
            lang = ""
            classes = list(el.get("class", [])) + list(
                code_el.get("class", [])
            )
            for cls in classes:
                if isinstance(cls, str) and cls.startswith("language-"):
                    lang = cls.replace("language-", "")
                    break
            # Also check parent div for language class
            parent = el.parent
            if not lang and parent and parent.name == "div":
                for cls in parent.get("class", []):
                    if isinstance(cls, str) and cls.startswith("language-"):
                        lang = cls.replace("language-", "")
                        break
            return f"\n```{lang}\n{raw_code.strip()}\n```\n\n"
        return f"\n```\n{text.strip()}\n```\n\n"

    def convert_details(self, el: Tag, text: str, **kwargs) -> str:
        """Convert <details> elements to blockquote with summary."""
        summary_el = el.find("summary")
        summary = summary_el.get_text(strip=True) if summary_el else "Details"

        # Get the content after the summary
        content_parts = []
        for child in el.children:
            if isinstance(child, Tag) and child.name == "summary":
                continue
            converted = (
                self.convert(str(child)) if isinstance(child, Tag) else str(child)
            )
            if converted.strip():
                content_parts.append(converted.strip())

        content = "\n".join(content_parts)
        # Indent content as blockquote
        indented = "\n".join(
            f"> {line}" if line.strip() else ">" for line in content.split("\n")
        )
        return f"\n> **{summary}**\n>\n{indented}\n\n"

    def convert_div(self, el: Tag, text: str, **kwargs) -> str:
        """Handle special div types: admonitions, embeds, doc objects."""
        classes = el.get("class", [])

        # Admonitions (tip, note, warning, etc.)
        if "admonition" in classes:
            return self._convert_admonition(el, classes)

        # marimo embed containers
        if "marimo-embed-container" in classes:
            iframe = el.find("iframe")
            if iframe and iframe.get("src"):
                return f"\n[Interactive marimo example]({iframe['src']})\n\n"
            return ""

        # Tabbed content sets
        if "tabbed-set" in classes:
            return self._convert_tabbed(el)

        # mkdocstrings doc signature blocks
        if "doc-signature" in classes or (
            "highlight" in classes and "doc-signature" in " ".join(classes)
        ):
            code_el = el.find("code")
            if code_el:
                raw = code_el.get_text()
                return f"\n```python\n{raw.strip()}\n```\n\n"

        # Doc contents - just pass through
        if "doc-contents" in classes:
            return f"\n{text}\n"

        # Default: return inner text
        return text

    def _convert_admonition(self, el: Tag, classes: list) -> str:
        """Convert admonition divs to blockquotes."""
        # Determine type
        admonition_type = "Note"
        for cls in classes:
            if cls != "admonition" and cls not in (
                "md-typeset",
                "inline",
                "end",
            ):
                admonition_type = cls.capitalize()
                break

        title_el = el.find("p", class_="admonition-title")
        title = title_el.get_text(strip=True) if title_el else admonition_type

        # Get content after title
        content_parts = []
        for child in el.children:
            if isinstance(child, Tag) and "admonition-title" in (
                child.get("class", [])
            ):
                continue
            converted = (
                self.convert(str(child)) if isinstance(child, Tag) else str(child)
            )
            if converted.strip():
                content_parts.append(converted.strip())

        content = "\n".join(content_parts)
        indented = "\n".join(
            f"> {line}" if line.strip() else ">" for line in content.split("\n")
        )
        return f"\n> **{title}**\n>\n{indented}\n\n"

    def _convert_tabbed(self, el: Tag) -> str:
        """Convert tabbed content to sections."""
        result = []
        contents = el.find_all("div", class_="tabbed-block")

        # Get label text from <label> elements inside .tabbed-labels
        label_texts = []
        labels_div = el.find("div", class_="tabbed-labels")
        if labels_div:
            for label in labels_div.find_all("label"):
                text = label.get_text(strip=True)
                if text:
                    label_texts.append(text)

        # Fallback: try tabbed-set__label class
        if not label_texts:
            for label in el.find_all("label", class_="tabbed-set__label"):
                text = label.get_text(strip=True)
                if text:
                    label_texts.append(text)

        for i, content in enumerate(contents):
            tab_label = label_texts[i] if i < len(label_texts) else f"Tab {i + 1}"
            converted = self.convert(str(content))
            result.append(f"**{tab_label}:**\n\n{converted.strip()}")

        return "\n\n".join(result) + "\n\n"

    def convert_a(self, el: Tag, text: str, **kwargs) -> str:
        """Convert links, resolving relative paths to absolute URLs."""
        href = el.get("href", "")

        # Skip headerlinks (permalink anchors)
        if "headerlink" in (el.get("class") or []):
            return ""

        if not text.strip():
            return ""

        # Resolve relative URLs to absolute
        if href and not href.startswith(("http://", "https://", "#", "mailto:")):
            # Build the absolute URL
            page_url = f"{self.base_url}/{self.page_path}"
            href = urljoin(page_url, href)

        if href:
            return f"[{text.strip()}]({href})"
        return text

    def convert_img(self, el: Tag, text: str, **kwargs) -> str:
        """Convert images with resolved URLs."""
        src = el.get("src", "")
        alt = el.get("alt", "")

        if not src:
            return ""

        # Skip tiny decorative images / icons
        width = el.get("width", "")
        if width and str(width).isdigit() and int(width) < 20:
            return ""

        # Resolve relative URLs
        if not src.startswith(("http://", "https://", "data:")):
            page_url = f"{self.base_url}/{self.page_path}"
            src = urljoin(page_url, src)

        return f"![{alt}]({src})"

    def _resolve_url(self, url: str) -> str:
        """Resolve a relative URL to an absolute URL."""
        if url and not url.startswith(("http://", "https://", "data:")):
            page_url = f"{self.base_url}/{self.page_path}"
            return urljoin(page_url, url)
        return url

    def convert_video(self, el: Tag, text: str, **kwargs) -> str:
        """Convert <video> elements to a markdown link."""
        src = el.get("src", "")
        # Also check for <source> child
        if not src:
            source = el.find("source")
            if source:
                src = source.get("src", "")
        if not src:
            return ""
        src = self._resolve_url(src)
        return f"\n[Video: {src}]({src})\n"

    def convert_figure(self, el: Tag, text: str, **kwargs) -> str:
        """Convert <figure> elements, preserving caption."""
        parts = []
        for child in el.children:
            if isinstance(child, Tag):
                if child.name == "figcaption":
                    caption = child.get_text(strip=True)
                    if caption:
                        parts.append(f"*{caption}*")
                else:
                    converted = self.convert(str(child)).strip()
                    if converted:
                        parts.append(converted)
        return "\n" + "\n\n".join(parts) + "\n\n"

    def convert_figcaption(self, el: Tag, text: str, **kwargs) -> str:
        """Convert <figcaption> to italicized text (standalone, outside figure)."""
        caption = el.get_text(strip=True)
        if caption:
            return f"\n*{caption}*\n"
        return ""

    def convert_table(self, el: Tag, text: str, **kwargs) -> str:
        """Convert tables to markdown tables."""
        rows = el.find_all("tr")
        if not rows:
            return text

        table_data: list[list[str]] = []
        for row in rows:
            cells = row.find_all(["th", "td"])
            row_data = []
            for cell in cells:
                # Convert cell content
                cell_text = self.convert(str(cell))
                # Clean up: collapse whitespace, remove newlines
                cell_text = re.sub(r"\s+", " ", cell_text).strip()
                # Escape pipe characters so they don't break the table
                cell_text = cell_text.replace("|", "\\|")
                row_data.append(cell_text)
            table_data.append(row_data)

        if not table_data:
            return text

        # Build markdown table
        result = []
        # Header
        result.append("| " + " | ".join(table_data[0]) + " |")
        result.append("| " + " | ".join("---" for _ in table_data[0]) + " |")
        # Body
        for row in table_data[1:]:
            # Pad row to match header length
            while len(row) < len(table_data[0]):
                row.append("")
            result.append("| " + " | ".join(row) + " |")

        return "\n" + "\n".join(result) + "\n\n"

    def convert_td(self, el: Tag, text: str, **kwargs) -> str:
        """Pass through td content without wrapping."""
        return text.strip()

    def convert_th(self, el: Tag, text: str, **kwargs) -> str:
        """Pass through th content without wrapping."""
        return text.strip()


def extract_title(soup: BeautifulSoup) -> str:
    """Extract the page title from the HTML."""
    title_el = soup.find("title")
    if title_el:
        title = title_el.get_text(strip=True)
        # Remove " - marimo" suffix
        if title.endswith(" - marimo"):
            title = title[: -len(" - marimo")]
        return title
    return ""


def clean_markdown(md: str) -> str:
    """Post-process markdown to clean up artifacts."""
    # Remove excessive blank lines (more than 2 consecutive)
    md = re.sub(r"\n{4,}", "\n\n\n", md)
    # Remove trailing whitespace on lines
    md = "\n".join(line.rstrip() for line in md.split("\n"))
    # Remove the pilcrow sign that appears in headerlinks
    md = md.replace("\u00b6", "")
    # Unescape Jinja2-escaped braces (\{\{ -> {{, \}\} -> }})
    md = md.replace("\\{\\{", "{{").replace("\\}\\}", "}}")
    # Strip leading/trailing whitespace
    md = md.strip()
    return md


def convert_page(html_path: Path, input_dir: Path, base_url: str) -> str | None:
    """Convert a single HTML page to markdown."""
    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")

    # Extract the article content
    article = soup.find("article", class_="md-content__inner")
    if not article:
        return None

    # Remove elements we don't want
    # Remove copy buttons from code blocks
    for btn in article.find_all("button", class_="md-clipboard"):
        btn.decompose()
    # Remove annotation markers
    for marker in article.find_all("span", class_="md-annotation"):
        marker.decompose()
    # Remove "Last updated" footer
    for aside in article.find_all("aside", class_="md-source-file"):
        aside.decompose()
    # Remove SVG icons
    for svg in article.find_all("svg"):
        svg.decompose()
    # Remove inline style tags
    for style in article.find_all("style"):
        style.decompose()

    title = extract_title(soup)

    # Calculate the page path relative to the input dir
    rel_path = html_path.parent.relative_to(input_dir)
    page_path = str(rel_path)
    if page_path == ".":
        page_path = ""
    page_path = page_path + "/"

    # Get canonical URL
    canonical = f"{base_url}/{page_path}".replace("//", "/").replace(":/", "://")

    # Convert to markdown
    converter = DocsMarkdownConverter(
        base_url=base_url,
        page_path=page_path,
        heading_style="ATX",
        bullets="-",
        strong_em_symbol="*",
        wrap=False,
        wrap_width=0,
        strip=["nav", "footer", "script", "style", "noscript"],
    )
    md = converter.convert(str(article))
    md = clean_markdown(md)

    # Add source URL as a comment at the top (the article already has an H1)
    header = f"<!-- Source: {canonical} -->\n\n"
    return header + md


def main():
    parser = argparse.ArgumentParser(description="Convert mkdocs HTML to markdown")
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Path to the built site directory",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="https://docs.marimo.io",
        help="Base URL for resolving links",
    )
    args = parser.parse_args()

    input_dir: Path = args.input_dir
    base_url: str = args.base_url

    if not input_dir.exists():
        print(f"Error: input directory {input_dir} does not exist")
        raise SystemExit(1)

    converted = 0
    skipped = 0

    for root, _dirs, files in os.walk(input_dir):
        for filename in files:
            if filename != "index.html":
                continue

            html_path = Path(root) / filename
            md = convert_page(html_path, input_dir, base_url)

            if md is None:
                skipped += 1
                continue

            # Write markdown alongside the HTML
            md_path = html_path.with_name("index.md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md)

            converted += 1

    print(f"Converted {converted} pages, skipped {skipped}")


if __name__ == "__main__":
    main()
