# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re
from textwrap import dedent

from marimo._runtime.patches import patch_jedi_parameter_completion


def google_docstring_to_markdown(docstring: str) -> str:
    """
    Converts a Google-style docstring to a rough Markdown format.

    Args:
        docstring (str): The raw Google-style docstring.

    Returns:
        str: A Markdown string that can be consumed by our doc-to-HTML converter.
    """
    if not docstring:
        return ""

    docstring_lines = docstring.splitlines()
    if len(docstring_lines) > 1:
        first_line = docstring_lines[0]
        dedented_lines = dedent("\n".join(docstring_lines[1:]))
        docstring = first_line + "\n" + dedented_lines

    # Simple approach: split and parse line by line
    lines = docstring.strip().splitlines()
    parsed_lines: list[str] = []
    arg_table: list[tuple[str, str, str]] = []
    attribute_table: list[tuple[str, str, str]] = []
    returns_table: list[tuple[str, str]] = []
    raises_table: list[tuple[str, str]] = []
    in_args = False
    in_attributes = False
    in_returns = False
    in_raises = False
    in_examples = False
    examples_lines: list[str] = []

    def _handle_arg_or_attribute(
        table: list[tuple[str, str, str]], stripped: str
    ) -> None:
        # Parse standard parameters: "arg_name (arg_type): description" or "arg_name: description"
        # This handles both typed and untyped parameters, with or without description
        match = re.match(r"^(\w+)(?:\s*\(([^)]+)\))?:\s*(.*)", stripped)
        if match:
            arg_name, arg_type, description = match.groups()
            table.append((arg_name, arg_type or "", description.strip()))
            return

        # Parse special parameters: "*args: description" or "**kwargs: description"
        if stripped.startswith("*args:"):
            table.append(("*args", "", stripped[6:].strip()))
            return
        if stripped.startswith("**kwargs:"):
            table.append(("**kwargs", "", stripped[9:].strip()))
            return

        # Handle continuation lines
        if not table:
            return

        current_name, current_type, current_desc = table[-1]
        stripped_content = stripped.strip()

        # Handle bullet points
        if stripped_content.startswith("- "):
            bullet_content = stripped_content[2:]
            new_desc = (
                current_desc + "<br>- " + bullet_content
                if current_desc
                else "- " + bullet_content
            )
            table[-1] = (current_name, current_type, new_desc)
            return

        # Check if we're inside a code block
        if "```" in current_desc and not current_desc.rstrip().endswith("```"):
            table[-1] = (
                current_name,
                current_type,
                current_desc + "\n" + stripped_content,
            )
            return

        # Regular continuation - add space separator
        table[-1] = (
            current_name,
            current_type,
            current_desc + " " + stripped_content,
        )

    # We'll store a simple summary until we see "Args:" or "Returns:" or "Raises:"
    for line in lines:
        # Only strip the first 4 spaces
        if line.startswith("    "):
            stripped = line[4:]
        else:
            stripped = line.strip()

        # Check for control keywords
        if re.match(r"^Args:\s*$", stripped):
            in_args = True
            in_attributes = False
            in_returns = False
            in_raises = False
            in_examples = False
            continue
        elif re.match(r"^Attributes:\s*$", stripped):
            in_args = False
            in_attributes = True
            in_returns = False
            in_raises = False
            in_examples = False
            continue
        elif re.match(r"^Returns?:\s*$", stripped):
            in_args = False
            in_attributes = False
            in_returns = True
            in_raises = False
            in_examples = False
            continue
        elif re.match(r"^Raises:\s*$", stripped):
            in_args = False
            in_attributes = False
            in_returns = False
            in_raises = True
            in_examples = False
            continue
        elif re.match(r"^Examples?:\s*$", stripped):
            in_args = False
            in_attributes = False
            in_returns = False
            in_raises = False
            in_examples = True
            continue

        if in_examples:
            # Just capture all lines for examples block
            examples_lines.append(stripped)
            continue

        # If within Args:
        if in_args:
            _handle_arg_or_attribute(arg_table, stripped)
            continue

        # If within Attributes:
        if in_attributes:
            _handle_arg_or_attribute(attribute_table, stripped)
            continue

        # If within Returns:
        if in_returns:
            # Typically: "    ReturnType: the big description"
            match = re.match(r"^([^:]+):\s*(.*)", stripped)
            if match:
                ret_type, description = match.groups()
                returns_table.append((ret_type.strip(), description.strip()))
            else:
                # Possibly just an indented line continuing
                if returns_table:
                    returns_table[-1] = (
                        returns_table[-1][0],
                        returns_table[-1][1] + " " + stripped.strip(),
                    )
            continue

        # If within Raises:
        if in_raises:
            # Google style typically: "    ErrorType: explanation"
            match = re.match(r"^([^:]+):\s*(.*)", stripped)
            if match:
                err_type, explanation = match.groups()
                # We'll just turn it into a "# Raises" heading
                # and bullet lines for each raise
                raises_table.append((err_type.strip(), explanation.strip()))
            else:
                # Possibly just an indented line continuing
                if raises_table and raises_table[-1][1].startswith("- **"):
                    raises_table[-1] = (
                        raises_table[-1][0],
                        raises_table[-1][1] + " " + stripped.strip(),
                    )
            continue

        # Otherwise, treat it as summary or normal text
        parsed_lines.append(stripped)

    # Build final output
    output: list[str] = []
    if parsed_lines:
        output.append("# Summary")
        output.append("\n".join(parsed_lines).strip())

    if examples_lines:
        output.append("\n# Examples")
        output.append("\n".join(examples_lines))

    if arg_table:
        output.append("\n# Arguments")
        output.append("| Parameter | Type | Description |")
        output.append("|-----------|------|-------------|")
        for arg_name, arg_type, desc in arg_table:
            # Process code blocks in the description
            processed_desc = _process_code_block_content(desc.strip())
            output.append(
                f"| `{arg_name}` | `{arg_type}` | {processed_desc} |"
            )

    if attribute_table:
        output.append("\n# Attributes")
        output.append("| Attribute | Type | Description |")
        output.append("|-----------|------|-------------|")
        for arg_name, arg_type, desc in attribute_table:
            # Process code blocks in the description
            processed_desc = _process_code_block_content(desc.strip())
            output.append(
                f"| `{arg_name}` | `{arg_type}` | {processed_desc} |"
            )

    if returns_table:
        output.append("\n# Returns")
        output.append("| Type | Description |")
        output.append("|------|-------------|")
        for ret_type, desc in returns_table:
            output.append(f"| `{ret_type}` | {desc.strip()} |")

    if raises_table:
        output.append("\n# Raises")
        for err_type, explanation in raises_table:
            output.append(f"- **{err_type}**: {explanation.strip()}")

    return "\n".join(output)


# See https://github.com/python-lsp/docstring-to-markdown?tab=readme-ov-file#extensibility
class MarimoConverter:
    priority = 100

    def __init__(self) -> None:
        patch_jedi_parameter_completion()

    SECTION_HEADERS = ["Args", "Returns", "Raises", "Examples"]

    def convert(self, docstring: str) -> str:
        return google_docstring_to_markdown(docstring)

    def can_convert(self, docstring: str) -> bool:
        for section in self.SECTION_HEADERS:
            if re.search(rf"{section}:\n", docstring):
                return True

        return False


def _process_code_block_content(description: str) -> str:
    """
    Process a description that may contain code blocks and convert them to HTML.

    Args:
        description (str): The description text that may contain ``` code blocks

    Returns:
        str: The description with code blocks converted to HTML <pre><code> tags
    """
    if "```" not in description:
        return description

    def replace_code_block(match: re.Match[str]) -> str:
        code_content = match.group(1).strip()
        if code_content.startswith("python\n"):
            code_content = code_content[7:]  # Remove "python\n"

        return (
            f"<pre><code>{code_content.replace(chr(10), '<br>')}</code></pre>"
        )

    return re.sub(
        r"```(.*?)```", replace_code_block, description, flags=re.DOTALL
    )
