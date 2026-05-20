# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
import mimetypes
import re
from html.parser import HTMLParser
from typing import TYPE_CHECKING, cast

from marimo import _loggers
from marimo._messaging.mimetypes import KnownMimeType
from marimo._runtime.virtual_file import read_virtual_file
from marimo._utils.data_uri import build_data_url

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

LOGGER = _loggers.marimo_logger()


class _HTMLAttributeReplacer(HTMLParser):
    """HTML parser that finds and replaces attribute values in specific tags.

    This parser traverses HTML strings and applies a custom replacement function
    to specified attributes in allowed tags.

    Example:
    ```python
    def upper_replacer(value: str) -> Optional[str]:
        return value.upper()


    replacer = HTMLAttributeReplacer(
        allowed_tags={"img"},
        allowed_attributes={"src"},
        replacer_fn=upper_replacer,
    )
    replacer.feed('<img src="test.png">')
    replacer.get_output()
    ```
    """

    def __init__(
        self,
        allowed_tags: set[str],
        allowed_attributes: set[str],
        replacer_fn: Callable[[str], str | None],
    ) -> None:
        """Initialize the HTML attribute replacer.

        Args:
            allowed_tags: Set of HTML tag names to process (e.g., {"img", "a"})
            allowed_attributes: Set of attribute names to process (e.g., {"src", "href"})
            replacer_fn: Function that takes an attribute value and returns
                        a replacement value, or None to keep the original
        """
        super().__init__()
        self.allowed_tags = {tag.lower() for tag in allowed_tags}
        self.allowed_attributes = {attr.lower() for attr in allowed_attributes}
        self.replacer_fn = replacer_fn
        self._output: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        """Handle opening tags, replacing attributes if applicable."""
        if tag.lower() in self.allowed_tags:
            # Process attributes for allowed tags
            new_attrs: list[tuple[str, str | None]] = []
            for attr_name, attr_value in attrs:
                if attr_name.lower() in self.allowed_attributes and attr_value:
                    # Apply the replacer function
                    replacement = self.replacer_fn(attr_value)
                    new_attrs.append(
                        (
                            attr_name,
                            replacement
                            if replacement is not None
                            else attr_value,
                        )
                    )
                else:
                    new_attrs.append((attr_name, attr_value))
            attrs = new_attrs

        # Reconstruct the tag
        attrs_str = self._format_attrs(attrs)
        self._output.append(f"<{tag}{attrs_str}>")

    def handle_endtag(self, tag: str) -> None:
        """Handle closing tags."""
        self._output.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        """Handle text content between tags."""
        self._output.append(data)

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        """Handle self-closing tags (e.g., <img />)."""
        if tag.lower() in self.allowed_tags:
            # Process attributes for allowed tags
            new_attrs: list[tuple[str, str | None]] = []
            for attr_name, attr_value in attrs:
                if attr_name.lower() in self.allowed_attributes and attr_value:
                    # Apply the replacer function
                    replacement = self.replacer_fn(attr_value)
                    new_attrs.append(
                        (
                            attr_name,
                            replacement
                            if replacement is not None
                            else attr_value,
                        )
                    )
                else:
                    new_attrs.append((attr_name, attr_value))
            attrs = new_attrs

        # Reconstruct the self-closing tag
        attrs_str = self._format_attrs(attrs)
        self._output.append(f"<{tag}{attrs_str} />")

    def handle_comment(self, data: str) -> None:
        """Preserve HTML comments."""
        self._output.append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        """Preserve declarations like DOCTYPE."""
        self._output.append(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        """Preserve processing instructions."""
        self._output.append(f"<?{data}>")

    def handle_charref(self, name: str) -> None:
        """Preserve character references like &#123;."""
        self._output.append(f"&#{name};")

    def handle_entityref(self, name: str) -> None:
        """Preserve entity references like &nbsp;."""
        self._output.append(f"&{name};")

    def _format_attrs(self, attrs: list[tuple[str, str | None]]) -> str:
        """Format attributes for output."""
        if not attrs:
            return ""
        formatted = []
        for name, value in attrs:
            if value is None:
                # Boolean attribute
                formatted.append(name)
            else:
                # Escape quotes in the value
                escaped_value = value.replace('"', "&quot;")
                formatted.append(f'{name}="{escaped_value}"')
        return " " + " ".join(formatted)

    def get_output(self) -> str:
        """Get the processed HTML output."""
        return "".join(self._output)


def replace_html_attributes(
    html: str,
    *,
    allowed_tags: set[str],
    allowed_attributes: set[str],
    replacer_fn: Callable[[str], str | None],
) -> str:
    """Replace attribute values in HTML using a custom function.

    Args:
        html: The HTML string to process
        allowed_tags: Set of HTML tag names to process (e.g., {"img", "a"})
        allowed_attributes: Set of attribute names to process (e.g., {"src", "href"})
        replacer_fn: Function that takes an attribute value and returns
                    a replacement value, or None to keep the original

    Returns:
        The processed HTML string with replaced attributes

    Example:
    ```python
    def virtual_file_replacer(value: str) -> Optional[str]:
        if value.startswith("./@file/"):
            return convert_to_data_uri(value)
        return None


    html = '<img src="./@file/123-test.png"><a href="https://example.com">Link</a>'
    result = replace_html_attributes(
        html,
        allowed_tags={"img", "a"},
        allowed_attributes={"src", "href"},
        replacer_fn=virtual_file_replacer,
    )
    ```
    """
    parser = _HTMLAttributeReplacer(
        allowed_tags=allowed_tags,
        allowed_attributes=allowed_attributes,
        replacer_fn=replacer_fn,
    )
    parser.feed(html)
    return parser.get_output()


# Virtual file pattern: ./@file/{byte_length}-{filename}
VIRTUAL_FILE_PATTERN = re.compile(r"^\./@file/(\d+)-(.+)$")


def _is_virtual_file_url(url: str) -> bool:
    """Check if a URL is a virtual file reference.

    Args:
        url: The URL to check

    Returns:
        True if the URL matches the virtual file pattern (./@file/{byte_length}-{filename})
    """
    return VIRTUAL_FILE_PATTERN.match(url) is not None


def _parse_virtual_file_url(url: str) -> tuple[int, str] | None:
    """Parse a virtual file URL into its components.

    Args:
        url: The virtual file URL (e.g., "./@file/29676-test.png")

    Returns:
        Tuple of (byte_length, filename) if the URL is valid, None otherwise
    """
    match = VIRTUAL_FILE_PATTERN.match(url)
    if not match:
        return None
    byte_length_str, filename = match.groups()
    return int(byte_length_str), filename


def _virtual_file_to_data_uri(virtual_file_url: str) -> str | None:
    """Convert a virtual file URL to a data URI.

    Args:
        virtual_file_url: The virtual file URL (e.g., "./@file/29676-test.png")

    Returns:
        A data URI string, or None if the conversion fails
    """
    parsed = _parse_virtual_file_url(virtual_file_url)
    if not parsed:
        return None

    byte_length, filename = parsed
    try:
        buffer_contents = read_virtual_file(filename, byte_length)
        mime_type = mimetypes.guess_type(filename)[0] or "text/plain"
        return build_data_url(
            cast(KnownMimeType, mime_type),
            base64.b64encode(buffer_contents),
        )
    except Exception as e:
        LOGGER.warning(
            "Failed to convert virtual file to data URI: %s. Error: %s",
            virtual_file_url,
            e,
        )
        return None


def replace_virtual_files_with_data_uris(
    html: str,
    allowed_tags: set[str],
    allowed_attributes: set[str] | None = None,
    max_inline_bytes: int | None = None,
) -> tuple[str, set[str]]:
    """Replace virtual file URLs with data URIs in HTML.

    This is a convenience function that uses replace_html_attributes with a
    virtual file to data URI replacer.

    Args:
        html: The HTML string to process
        allowed_tags: Set of HTML tag names to process
        allowed_attributes: Set of attribute names to process. Defaults to {"src", "href"}
        max_inline_bytes: Maximum file size in bytes to inline. Files larger
            than this limit are skipped. None means no limit.

    Returns:
        Tuple of (processed_html, replaced_files) where:
        - processed_html: The HTML string with virtual files replaced by data URIs
        - replaced_files: Set of virtual file URLs that were successfully replaced

    Example:
    ```python
    html = '<img src="./@file/29676-25241121-ZSE6dgpj.png">'
    result, replaced = replace_virtual_files_with_data_uris(
        html, allowed_tags={"img"}
    )
    # replaced = {"./@file/29676-25241121-ZSE6dgpj.png"}
    ```
    """

    if allowed_attributes is None:
        allowed_attributes = {"src", "href", "data"}

    replaced_files: set[str] = set()

    def replacer(value: str) -> str | None:
        """Replace virtual file URLs with data URIs."""
        if _is_virtual_file_url(value):
            if max_inline_bytes is not None:
                parsed = _parse_virtual_file_url(value)
                if parsed and parsed[0] > max_inline_bytes:
                    LOGGER.info(
                        "Skipping virtual file %s (%d bytes exceeds"
                        " %d byte inline limit)",
                        value,
                        parsed[0],
                        max_inline_bytes,
                    )
                    # Return a text placeholder so users see a clear
                    # message instead of a broken ./@file/ link.
                    msg = (
                        f"File too large to inline "
                        f"({parsed[0]} bytes, limit {max_inline_bytes})"
                    )
                    return build_data_url(
                        "text/plain",
                        base64.b64encode(msg.encode("utf-8")),
                    )
            result = _virtual_file_to_data_uri(value)
            if result is not None:
                # Track successfully replaced files
                replaced_files.add(value)
            return result
        return None

    processed_html = replace_html_attributes(
        html=html,
        allowed_tags=allowed_tags,
        allowed_attributes=allowed_attributes,
        replacer_fn=replacer,
    )

    return processed_html, replaced_files


# Public folder file pattern: public/{path} or ./public/{path}
_PUBLIC_FILE_PATTERN = re.compile(r"^(?:\./)?public/(.+)$")


def _resolve_public_file(public_dir: Path, relpath: str) -> Path | None:
    """Resolve a `public/`-prefixed path against the public dir.

    Returns the resolved path if it points to an existing regular file
    strictly inside `public_dir`, or None otherwise. Rejects path traversal
    and symlinks that escape the public directory.
    """
    try:
        # `strict=True` ensures the file exists.
        candidate = (public_dir / relpath).resolve(strict=True)
        public_resolved = public_dir.resolve(strict=True)
    except (OSError, ValueError):
        return None

    # Containment check: the resolved file must live under the resolved
    # public directory (catches path traversal and symlink escapes).
    try:
        candidate.relative_to(public_resolved)
    except ValueError:
        return None

    if not candidate.is_file():
        return None

    return candidate


def replace_public_files_with_data_uris(
    html: str,
    public_dir: Path,
    *,
    allowed_tags: set[str] | None = None,
    allowed_attributes: set[str] | None = None,
    max_inline_bytes: int | None = None,
) -> tuple[str, set[str]]:
    """Inline `public/`-prefixed file references as data URIs.

    Scans `html` for media tag attributes (e.g. `<img src="public/...">`),
    reads the referenced file from the notebook's `public/` folder, and
    replaces the attribute value with a base64-encoded data URI so the
    HTML can be served standalone. Paths that escape `public_dir` (via
    `..` segments or symlinks) are rejected and left unchanged.

    Args:
        html: The HTML string to process.
        public_dir: Path to the notebook's `public/` directory.
        allowed_tags: Tags to scan. Defaults to {"img", "audio", "video",
            "source"}.
        allowed_attributes: Attributes to scan. Defaults to {"src"}.
        max_inline_bytes: Maximum file size to inline. Larger files are
            left as-is. None means no limit.

    Returns:
        Tuple of (processed_html, replaced_paths) where `replaced_paths`
        is the set of attribute values that were successfully inlined.
    """
    if allowed_tags is None:
        allowed_tags = {"img", "audio", "video", "source"}
    if allowed_attributes is None:
        allowed_attributes = {"src"}

    replaced: set[str] = set()

    # If the public directory does not exist, there is nothing to inline.
    if not public_dir.exists():
        return html, replaced

    def replacer(value: str) -> str | None:
        match = _PUBLIC_FILE_PATTERN.match(value)
        if not match:
            return None
        relpath = match.group(1)
        resolved = _resolve_public_file(public_dir, relpath)
        if resolved is None:
            return None
        try:
            file_bytes = resolved.read_bytes()
        except OSError as e:
            LOGGER.warning(
                "Failed to read public file %s during export: %s", value, e
            )
            return None
        if max_inline_bytes is not None and len(file_bytes) > max_inline_bytes:
            LOGGER.info(
                "Skipping public file %s (%d bytes exceeds %d byte inline"
                " limit)",
                value,
                len(file_bytes),
                max_inline_bytes,
            )
            return None
        mime_type = mimetypes.guess_type(resolved.name)[0] or "text/plain"
        replaced.add(value)
        return build_data_url(
            cast(KnownMimeType, mime_type),
            base64.b64encode(file_bytes),
        )

    processed_html = replace_html_attributes(
        html=html,
        allowed_tags=allowed_tags,
        allowed_attributes=allowed_attributes,
        replacer_fn=replacer,
    )
    return processed_html, replaced
