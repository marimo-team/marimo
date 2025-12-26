# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
import mimetypes
import re
from html.parser import HTMLParser
from typing import Callable, Optional, cast

from marimo import _loggers
from marimo._messaging.mimetypes import KnownMimeType
from marimo._runtime.virtual_file import read_virtual_file
from marimo._utils.data_uri import build_data_url

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
        replacer_fn: Callable[[str], Optional[str]],
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
        self, tag: str, attrs: list[tuple[str, Optional[str]]]
    ) -> None:
        """Handle opening tags, replacing attributes if applicable."""
        if tag.lower() in self.allowed_tags:
            # Process attributes for allowed tags
            new_attrs: list[tuple[str, Optional[str]]] = []
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
        self, tag: str, attrs: list[tuple[str, Optional[str]]]
    ) -> None:
        """Handle self-closing tags (e.g., <img />)."""
        if tag.lower() in self.allowed_tags:
            # Process attributes for allowed tags
            new_attrs: list[tuple[str, Optional[str]]] = []
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

    def _format_attrs(self, attrs: list[tuple[str, Optional[str]]]) -> str:
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
    replacer_fn: Callable[[str], Optional[str]],
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


def _parse_virtual_file_url(url: str) -> Optional[tuple[int, str]]:
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


def _virtual_file_to_data_uri(virtual_file_url: str) -> Optional[str]:
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
    allowed_attributes: Optional[set[str]] = None,
) -> tuple[str, set[str]]:
    """Replace virtual file URLs with data URIs in HTML.

    This is a convenience function that uses replace_html_attributes with a
    virtual file to data URI replacer.

    Args:
        html: The HTML string to process
        allowed_tags: Set of HTML tag names to process
        allowed_attributes: Set of attribute names to process. Defaults to {"src", "href"}

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

    def replacer(value: str) -> Optional[str]:
        """Replace virtual file URLs with data URIs."""
        if _is_virtual_file_url(value):
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
