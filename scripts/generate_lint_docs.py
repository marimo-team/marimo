# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = []
#
# [tool.uv]
# exclude-newer = "2025-06-27T12:38:25.742953-04:00"
# ///
"""Generate documentation for marimo's lint rules.

This script automatically generates comprehensive documentation for all lint rules
in the marimo codebase, including:
- Main rules index page with categorized listings
- Individual rule pages with detailed explanations
- Validation of rule metadata and structure

Inspired by Ruff's documentation structure but adapted for marimo's style.
"""

from __future__ import annotations

import ast
import re
import textwrap
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class Severity(Enum):
    """Severity levels for diagnostic errors."""
    FORMATTING = "formatting"
    # Retained for future use: RUNTIME severity is intended for runtime-related lint rules.
    RUNTIME = "runtime"
    BREAKING = "breaking"


@dataclass
class RuleInfo:
    """Information about a lint rule extracted from source code."""
    code: str
    name: str
    description: str
    severity: Severity
    fixable: bool
    docstring: str
    file_path: Path
    class_name: str


# Add marimo to the path so we can import it
MARIMO_ROOT = Path(__file__).parent.parent


def extract_rule_info_from_file(file_path: Path) -> list[RuleInfo]:
    """Extract rule information from a Python file."""
    content = file_path.read_text()
    tree = ast.parse(content)

    rules = []

    for node in ast.walk(tree):
        if (isinstance(node, ast.ClassDef) and
            any(isinstance(base, ast.Name) and base.id in ["LintRule", "GraphRule"] for base in node.bases)):

            # Extract class attributes
            rule_data = {}

            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            attr_name = target.id
                            if attr_name in ["code", "name", "description", "severity", "fixable"]:
                                if isinstance(item.value, ast.Constant):
                                    rule_data[attr_name] = item.value.value
                                elif isinstance(item.value, ast.Attribute):
                                    # Handle Severity.BREAKING etc
                                    if (isinstance(item.value.value, ast.Name) and
                                        item.value.value.id == "Severity"):
                                        severity_name = item.value.attr
                                        rule_data[attr_name] = Severity(severity_name.lower())

            # Extract docstring
            docstring = ""
            if (node.body and isinstance(node.body[0], ast.Expr) and
                isinstance(node.body[0].value, ast.Constant) and
                isinstance(node.body[0].value.value, str)):
                docstring = node.body[0].value.value

            # Create rule info if we have required data
            if all(key in rule_data for key in ["code", "name", "description", "severity", "fixable"]):
                rules.append(RuleInfo(
                    code=rule_data["code"],
                    name=rule_data["name"],
                    description=rule_data["description"],
                    severity=rule_data["severity"],
                    fixable=rule_data["fixable"],
                    docstring=docstring,
                    file_path=file_path,
                    class_name=node.name
                ))

    return rules


def discover_all_rules() -> dict[str, RuleInfo]:
    """Discover all lint rules that are actually registered in the codebase."""
    # First, get the registered rule codes from the init files
    breaking_init = MARIMO_ROOT / "marimo" / "_lint" / "rules" / "breaking" / "__init__.py"
    formatting_init = MARIMO_ROOT / "marimo" / "_lint" / "rules" / "formatting" / "__init__.py"

    registered_codes = set()

    # Parse the breaking rules init file
    try:
        content = breaking_init.read_text()
        # Extract codes from BREAKING_RULE_CODES dictionary
        for line in content.split('\n'):
            if '"MB' in line and ':' in line:
                # Extract the code between quotes
                start = line.find('"MB')
                if start != -1:
                    end = line.find('"', start + 1)
                    if end != -1:
                        code = line[start + 1:end]
                        registered_codes.add(code)
    except Exception as e:
        print(f"Warning: Could not parse breaking rules init: {e}")

    # Parse the formatting rules init file
    try:
        content = formatting_init.read_text()
        # Extract codes from FORMATTING_RULE_CODES dictionary
        for line in content.split('\n'):
            if '"MF' in line and ':' in line:
                # Extract the code between quotes
                start = line.find('"MF')
                if start != -1:
                    end = line.find('"', start + 1)
                    if end != -1:
                        code = line[start + 1:end]
                        registered_codes.add(code)
    except Exception as e:
        print(f"Warning: Could not parse formatting rules init: {e}")

    # Now discover rules from source files
    rules_dir = MARIMO_ROOT / "marimo" / "_lint" / "rules"
    rule_files = list(rules_dir.rglob("*.py"))

    all_rules = {}

    for file_path in rule_files:
        if file_path.name in ["__init__.py", "base.py"]:
            continue

        try:
            rules = extract_rule_info_from_file(file_path)
            for rule in rules:
                # Only include rules that are actually registered
                if rule.code in registered_codes:
                    all_rules[rule.code] = rule
                else:
                    print(f"Skipping unregistered rule: {rule.code} ({rule.class_name})")
        except Exception as e:
            print(f"Warning: Could not parse {file_path}: {e}")

    return all_rules


def get_severity_info(severity: Severity) -> tuple[str, str, str]:
    """Get display information for a severity level."""
    severity_map = {
        Severity.BREAKING: ("🚨", "Breaking", "These errors prevent notebook execution"),
        Severity.RUNTIME: ("⚠️", "Runtime", "These issues may cause runtime problems"),
        Severity.FORMATTING: ("✨", "Formatting", "These are style and formatting issues"),
    }
    return severity_map.get(severity, ("❓", "Unknown", ""))


def validate_rule_info(rule: RuleInfo) -> list[str]:
    """Validate that a rule has all required information."""
    issues = []

    # Check required attributes are present and valid
    if not rule.code:
        issues.append("Missing rule code")
    elif not re.match(r'^M[BRF]\d{3}$', rule.code):
        issues.append(f"Invalid rule code format: {rule.code} (expected MB###, MR###, or MF###)")

    if not rule.name:
        issues.append("Missing rule name")

    if not rule.description:
        issues.append("Missing rule description")

    if not isinstance(rule.severity, Severity):
        issues.append(f"Invalid severity: {rule.severity}")

    if not isinstance(rule.fixable, bool):
        issues.append(f"Fixable must be a boolean, got {type(rule.fixable)}")

    # Validate docstring exists and is properly formatted
    if not rule.docstring:
        issues.append("Missing docstring")
    else:
        lines = rule.docstring.split('\n')
        first_line = lines[0].strip() if lines else ""
        if first_line and ':' in first_line:
            docstring_code = first_line.split(':')[0].strip()
            if docstring_code != rule.code:
                issues.append(f"Docstring code '{docstring_code}' doesn't match class code '{rule.code}'")

    # Validate rule code matches severity prefix
    code_prefix = rule.code[:2]
    expected_prefixes = {
        Severity.BREAKING: "MB",
        Severity.RUNTIME: "MR",
        Severity.FORMATTING: "MF"
    }
    expected_prefix = expected_prefixes.get(rule.severity)
    if expected_prefix and code_prefix != expected_prefix:
        issues.append(f"Rule code prefix '{code_prefix}' doesn't match severity '{rule.severity.value}' (expected '{expected_prefix}')")

    return issues


def get_rule_details(rule: RuleInfo) -> dict[str, Any]:
    """Extract detailed information about a rule."""
    if not rule.docstring:
        raise ValueError(f"Rule {rule.code} ({rule.class_name}) must have a docstring")

    # Remove the first line (rule code/description) and dedent the rest
    lines = rule.docstring.split('\n')
    full_description = lines[0] if lines else rule.description

    # Join everything after the first line and dedent it
    remaining_content = '\n'.join(lines[1:]) if len(lines) > 1 else ""
    dedented_content = textwrap.dedent(remaining_content)
    dedented_lines = dedented_content.split('\n')

    # Parse structured sections from dedented content
    sections = {}
    current_section = None
    current_content = []

    for line in dedented_lines:
        stripped = line.strip()

        # Check for section headers
        if stripped.startswith('## '):
            # Save previous section
            if current_section and current_content:
                sections[current_section] = '\n'.join(current_content).strip()

            # Start new section
            current_section = stripped[3:].strip()
            current_content = []
        elif current_section:
            # Add content to current section
            current_content.append(line)

    # Save last section
    if current_section and current_content:
        sections[current_section] = '\n'.join(current_content).strip()

    return {
        'code': rule.code,
        'name': rule.name,
        'description': rule.description,
        'severity': rule.severity,
        'fixable': rule.fixable,
        'docstring': rule.docstring,
        'full_description': full_description,
        'sections': sections,
        'file_path': str(rule.file_path.relative_to(MARIMO_ROOT)),
        'class_name': rule.class_name,
    }


def generate_main_index_page(rules_by_severity: dict[Severity, list[dict[str, Any]]]) -> str:
    """Generate the main lint rules index page."""
    content = """# Lint Rules

marimo includes a comprehensive linting system that helps you write better, more reliable notebooks. The linter checks for various issues that could prevent your notebook from running correctly or cause confusion.

## How to Use

You can run the linter using the CLI:

```bash
# Check all notebooks in current directory
marimo check .

# Check specific files
marimo check notebook1.py notebook2.py

# Auto-fix fixable issues
marimo check --fix .
```

## Rule Categories

marimo's lint rules are organized into three main categories based on their severity:

"""

    for severity in [Severity.BREAKING, Severity.RUNTIME, Severity.FORMATTING]:
        if severity not in rules_by_severity:
            continue

        icon, name, description = get_severity_info(severity)
        rules = rules_by_severity[severity]

        content += f"### {icon} {name} Rules\n\n"
        content += f"{description}.\n\n"

        # Create table of rules
        content += "| Code | Name | Description | Fixable |\n"
        content += "|------|------|-------------|----------|\n"

        for rule in sorted(rules, key=lambda r: r['code']):
            fixable_icon = "🛠️" if rule['fixable'] else "❌"
            filename = rule['name'].replace("-", "_") + ".md"
            rule_link = f"[{rule['code']}](rules/{filename})"
            content += f"| {rule_link} | {rule['name']} | {rule['description']} | {fixable_icon} |\n"

        content += "\n"

    content += """## Legend

- 🛠️ = Automatically fixable with `marimo check --fix`
- ❌ = Not automatically fixable

## Configuration

Most lint rules are enabled by default. You can configure the linter behavior through marimo's configuration system.

## Related Documentation

- [Understanding Errors](../understanding_errors/index.md) - Detailed explanations of common marimo errors
- [CLI Reference](../../cli.md) - Complete CLI documentation including `marimo check`
"""

    return content


def generate_rule_page(rule_details: dict[str, Any]) -> str:
    """Generate documentation page for an individual rule."""
    rule = rule_details
    icon, severity_name, _ = get_severity_info(rule['severity'])

    content = f"""# {rule['code']}: {rule['name']}

{icon} **{severity_name}** {'🛠️ Fixable' if rule['fixable'] else '❌ Not Fixable'}

"""

    # Add the first line of the docstring as main description
    if rule['full_description'] and rule['full_description'] != rule['description']:
        # Split the first line from the rest
        desc_lines = rule['full_description'].split('.')
        if len(desc_lines) > 1:
            main_desc = desc_lines[0] + '.'
            rest_desc = '.'.join(desc_lines[1:]).strip()
            if rest_desc:
                content += f"{main_desc}\n\n{rest_desc}\n\n"
            else:
                content += f"{main_desc}\n\n"
        else:
            content += f"{rule['full_description']}\n\n"
    else:
        content += f"{rule['description']}\n\n"

    # Add structured sections from docstring
    sections = rule.get('sections', {})

    # Add sections in preferred order
    preferred_order = [
        'What it does',
        'Why is this bad?',
        'Examples',
        'How to fix',
        'References'
    ]

    for section_name in preferred_order:
        if section_name in sections:
            content += f"## {section_name}\n\n{sections[section_name]}\n\n"

    # Add any remaining sections not in the preferred order
    for section_name, section_content in sections.items():
        if section_name not in preferred_order:
            content += f"## {section_name}\n\n{section_content}\n\n"

    # Add default sections if not present in docstring
    if 'References' not in sections:
        content += "## References\n\n"
        content += "- [Understanding Errors](../understanding_errors/index.md)\n"
        content += f"- [Rule implementation]({_get_github_link(rule)})\n"

    return content


def _get_github_link(rule_details: dict[str, Any]) -> str:
    """Generate GitHub link for rule implementation."""
    file_path = rule_details['file_path']
    return f"https://github.com/marimo-team/marimo/blob/main/{file_path}"


def validate_mkdocs_integration(all_rules: dict[str, RuleInfo]) -> list[str]:
    """Validate that all generated rule pages are included in mkdocs.yml."""
    issues = []

    # Read mkdocs.yml
    mkdocs_path = MARIMO_ROOT / "mkdocs.yml"
    if not mkdocs_path.exists():
        issues.append("mkdocs.yml not found")
        return issues

    mkdocs_content = mkdocs_path.read_text()

    # Check if main lint rules index is in mkdocs
    if "guides/lint_rules/index.md" not in mkdocs_content:
        issues.append("Main lint rules page (guides/lint_rules/index.md) not found in mkdocs.yml")

    # Check if each rule page is in mkdocs
    for code, rule in all_rules.items():
        filename = rule.name.replace("-", "_") + ".md"
        rule_path = f"guides/lint_rules/rules/{filename}"

        if rule_path not in mkdocs_content:
            issues.append(f"Rule page {rule_path} not found in mkdocs.yml")

    return issues


def main() -> None:
    """Generate all lint rule documentation."""
    print("Generating marimo lint rules documentation...")

    # Discover all rules
    all_rules = discover_all_rules()
    print(f"📋 Discovered {len(all_rules)} rules")

    # Validate all rules first
    validation_issues = {}
    for code, rule in all_rules.items():
        issues = validate_rule_info(rule)
        if issues:
            validation_issues[code] = issues

    # Check for duplicate rule codes and names across all rules
    codes_seen = set()
    names_seen = set()
    global_issues = []

    for code, rule in all_rules.items():
        if code in codes_seen:
            global_issues.append(f"Duplicate rule code: {code}")
        codes_seen.add(code)

        if rule.name in names_seen:
            global_issues.append(f"Duplicate rule name: {rule.name}")
        names_seen.add(rule.name)

    # Check mkdocs integration
    mkdocs_issues = validate_mkdocs_integration(all_rules)

    if validation_issues or global_issues or mkdocs_issues:
        print("❌ Validation issues found:")
        if global_issues:
            print("  Global issues:")
            for issue in global_issues:
                print(f"    - {issue}")
        if mkdocs_issues:
            print("  mkdocs.yml issues:")
            for issue in mkdocs_issues:
                print(f"    - {issue}")
        for code, issues in validation_issues.items():
            print(f"  {code}:")
            for issue in issues:
                print(f"    - {issue}")
        return

    print(f"✅ Validated {len(all_rules)} rules and mkdocs.yml integration")

    # Organize rules by severity
    rules_by_severity: dict[Severity, list[dict[str, Any]]] = {}
    for code, rule in all_rules.items():
        rule_details = get_rule_details(rule)
        severity = rule_details['severity']

        if severity not in rules_by_severity:
            rules_by_severity[severity] = []
        rules_by_severity[severity].append(rule_details)

    # Create output directories
    docs_dir = MARIMO_ROOT / "docs" / "guides" / "lint_rules"
    rules_dir = docs_dir / "rules"

    docs_dir.mkdir(parents=True, exist_ok=True)
    rules_dir.mkdir(parents=True, exist_ok=True)

    # Generate main index page
    print("📝 Generating main index page...")
    main_content = generate_main_index_page(rules_by_severity)
    (docs_dir / "index.md").write_text(main_content)

    # Generate individual rule pages
    print("📝 Generating individual rule pages...")
    for code, rule in all_rules.items():
        rule_details = get_rule_details(rule)
        rule_content = generate_rule_page(rule_details)

        # Use the human-readable name for the filename
        filename = rule.name.replace("-", "_") + ".md"
        rule_file = rules_dir / filename
        rule_file.write_text(rule_content)
        print(f"  Generated {rule_file.name}")

    print(f"✅ Generated documentation for {len(all_rules)} rules")
    print(f"📁 Documentation written to: {docs_dir}")


if __name__ == "__main__":
    main()
