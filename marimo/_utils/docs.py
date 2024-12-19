# Copyright 2024 Marimo. All rights reserved.
import re
from textwrap import dedent


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
        # Typically: "    arg_name (arg_type): description"
        match = re.match(r"^(\w+)\s*\(([^)]+)\):\s*(.*)", stripped)
        if match:
            arg_name, arg_type, description = match.groups()
            table.append((arg_name, arg_type, description.strip()))
        else:
            # Fallback to "    arg_name: description"
            match = re.match(r"^(\w+)\s*:\s*(.*)", stripped)
            if match:
                arg_name, description = match.groups()
                table.append((arg_name, "", description.strip()))
            else:
                # Possibly just an indented line continuing the description
                if table:
                    table[-1] = (
                        table[-1][0],
                        table[-1][1],
                        table[-1][2] + " " + stripped.strip(),
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
            output.append(f"| `{arg_name}` | `{arg_type}` | {desc.strip()} |")

    if attribute_table:
        output.append("\n# Attributes")
        output.append("| Attribute | Type | Description |")
        output.append("|-----------|------|-------------|")
        for arg_name, arg_type, desc in attribute_table:
            output.append(f"| `{arg_name}` | `{arg_type}` | {desc.strip()} |")

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
