# Copyright 2024 Marimo. All rights reserved.
"""
Snapshot tests for domain-level dependencies.

This test tracks dependencies between second-level folders (domains) like
_messaging, _runtime, _ast, etc. It helps prevent unwanted coupling and
tracks architectural changes over time.
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest
from inline_snapshot import snapshot


def load_dag() -> dict[str, list[str]]:
    """Load the DAG from the JSON file at the repo root."""
    dag_path = Path(__file__).parent.parent.parent / "dag.json"
    if not dag_path.exists():
        pytest.skip(
            "dag.json not found - run: "
            "uvx ruff@0.13.2 analyze graph --direction dependents "
            "--detect-string-imports > dag.json"
        )

    with open(dag_path) as f:
        return json.load(f)


def extract_domain(file_path: str) -> str | None:
    """
    Extract the domain (second-level folder) from a file path.

    Examples:
        marimo/_runtime/runtime.py -> _runtime
        marimo/_messaging/ops.py -> _messaging
        marimo/__init__.py -> __init__
        tests/_runtime/test_runtime.py -> tests/_runtime
    """
    parts = Path(file_path).parts

    if len(parts) < 2:
        return None

    # Handle marimo/* paths
    if parts[0] == "marimo":
        if len(parts) == 2:
            # marimo/__init__.py or marimo/_version.py
            return parts[1].replace(".py", "")
        return parts[1]  # marimo/_runtime/...

    # Handle tests/* paths
    if parts[0] == "tests":
        if len(parts) == 2:
            return "tests"
        return f"tests/{parts[1]}"

    # Handle other top-level paths (docs, dagger, scripts)
    return parts[0]


def build_domain_dag(file_dag: dict[str, list[str]]) -> dict[str, set[str]]:
    """
    Build a domain-level DAG from the file-level DAG.

    Returns a dict mapping domain -> set of domains it depends on.
    """
    domain_dag: dict[str, set[str]] = defaultdict(set)

    for file_path, dependencies in file_dag.items():
        source_domain = extract_domain(file_path)
        if source_domain is None:
            continue

        for dep_path in dependencies:
            target_domain = extract_domain(dep_path)
            if target_domain is None:
                continue

            # Skip self-dependencies
            if source_domain == target_domain:
                continue

            domain_dag[source_domain].add(target_domain)

    # Convert sets to sorted lists for stable output
    return {
        domain: sorted(deps) for domain, deps in sorted(domain_dag.items())
    }


def format_domain_dependencies(domain_dag: dict[str, list[str]]) -> str:
    """Format the domain DAG as a readable string."""
    lines = ["# Domain Dependencies", ""]

    # Separate marimo domains from test domains
    marimo_domains = {
        k: v for k, v in domain_dag.items() if not k.startswith("tests")
    }
    test_domains = {
        k: v for k, v in domain_dag.items() if k.startswith("tests")
    }

    lines.append("## Marimo Domains")
    lines.append("")
    for domain in sorted(marimo_domains.keys()):
        deps = marimo_domains[domain]
        lines.append(f"{domain}:")
        if deps:
            for dep in deps:
                lines.append(f"  -> {dep}")
        else:
            lines.append("  (no external dependencies)")
        lines.append("")

    if test_domains:
        lines.append("## Test Domains")
        lines.append("")
        for domain in sorted(test_domains.keys()):
            deps = test_domains[domain]
            lines.append(f"{domain}:")
            if deps:
                for dep in deps:
                    lines.append(f"  -> {dep}")
            else:
                lines.append("  (no external dependencies)")
            lines.append("")

    return "\n".join(lines)


def create_mermaid_diagram(domain_dag: dict[str, list[str]]) -> str:
    """Create a Mermaid diagram of domain dependencies."""
    lines = ["```mermaid", "graph TD"]

    # Only include marimo domains (exclude tests for clarity)
    marimo_domains = {
        k: v for k, v in domain_dag.items() if not k.startswith("tests")
    }

    # Create nodes with better labels
    for domain in sorted(marimo_domains.keys()):
        label = domain.replace("_", "").replace(".", "")
        lines.append(f"    {label}[{domain}]")

    # Create edges
    for source, targets in sorted(marimo_domains.items()):
        source_label = source.replace("_", "").replace(".", "")
        for target in targets:
            if not target.startswith(
                "tests"
            ):  # Only show marimo -> marimo deps
                target_label = target.replace("_", "").replace(".", "")
                lines.append(f"    {source_label} --> {target_label}")

    lines.append("```")
    return "\n".join(lines)


def analyze_domain_metrics(domain_dag: dict[str, list[str]]) -> dict[str, Any]:
    """Analyze metrics about domain dependencies."""
    marimo_domains = {
        k: v for k, v in domain_dag.items() if not k.startswith("tests")
    }

    # Calculate fan-out (how many domains each domain depends on)
    fan_out = {domain: len(deps) for domain, deps in marimo_domains.items()}

    # Calculate fan-in (how many domains depend on each domain)
    fan_in: dict[str, int] = defaultdict(int)
    for deps in marimo_domains.values():
        for dep in deps:
            if not dep.startswith("tests"):
                fan_in[dep] += 1

    # Get all marimo domains
    all_domains = set(marimo_domains.keys())
    for deps in marimo_domains.values():
        all_domains.update(d for d in deps if not d.startswith("tests"))

    return {
        "total_domains": len(all_domains),
        "total_edges": sum(len(deps) for deps in marimo_domains.values()),
        "highest_fan_out": sorted(
            fan_out.items(), key=lambda x: x[1], reverse=True
        )[:10],
        "highest_fan_in": sorted(
            fan_in.items(), key=lambda x: x[1], reverse=True
        )[:10],
    }


def format_metrics(metrics: dict[str, Any]) -> str:
    """Format metrics as a readable string."""
    lines = [
        "# Domain Metrics",
        "",
        f"Total domains: {metrics['total_domains']}",
        f"Total dependencies: {metrics['total_edges']}",
        "",
        "## Highest Fan-Out (domains with most dependencies):",
        "",
    ]

    for domain, count in metrics["highest_fan_out"]:
        lines.append(f"  {domain}: {count} dependencies")

    lines.extend(
        [
            "",
            "## Highest Fan-In (most depended-upon domains):",
            "",
        ]
    )

    for domain, count in metrics["highest_fan_in"]:
        lines.append(f"  {domain}: {count} dependents")

    return "\n".join(lines)


def test_domain_dependencies_snapshot() -> None:
    """
    Snapshot test for domain-level dependencies.

    This test will fail if:
    - New domain dependencies are added
    - Existing domain dependencies are removed
    - The structure of domain relationships changes

    This is intentional to make architectural changes explicit.
    """
    file_dag = load_dag()
    domain_dag = build_domain_dag(file_dag)

    # Create comprehensive output
    output_parts = [
        format_domain_dependencies(domain_dag),
        "",
        format_metrics(analyze_domain_metrics(domain_dag)),
        "",
        create_mermaid_diagram(domain_dag),
    ]

    output = "\n".join(output_parts)
    assert output == snapshot()


def test_domain_dag_json_snapshot() -> None:
    """
    Snapshot test for the domain DAG in JSON format.

    Useful for programmatic analysis.
    """
    file_dag = load_dag()
    domain_dag = build_domain_dag(file_dag)

    # Convert to JSON-serializable format
    assert domain_dag == snapshot()


def test_core_domain_isolation() -> None:
    """
    Test that core domains maintain proper isolation.

    This enforces architectural rules:
    - _ast should not depend on _runtime
    - _utils should not depend on domain logic
    - _config should be standalone
    """
    file_dag = load_dag()
    domain_dag = build_domain_dag(file_dag)

    violations = []

    # _utils should only depend on other _utils or stdlib
    if "_utils" in domain_dag:
        forbidden = [
            "_runtime",
            "_ast",
            "_messaging",
            "_plugins",
            "_server",
            "_sql",
            "_data",
            "_save",
            "_output",
        ]
        for dep in domain_dag["_utils"]:
            if dep in forbidden:
                violations.append(f"_utils should not depend on {dep}")

    # _ast should not depend on _runtime (but _runtime can depend on _ast)
    if "_ast" in domain_dag and "_runtime" in domain_dag["_ast"]:
        violations.append(
            "_ast should not depend on _runtime (layer violation)"
        )

    # _config should have minimal dependencies
    if "_config" in domain_dag:
        allowed = ["_utils", "__init__"]
        for dep in domain_dag["_config"]:
            if not dep.startswith("tests") and dep not in allowed:
                violations.append(f"_config should not depend on {dep}")

    if violations:
        msg = "Domain isolation violations found:\n" + "\n".join(
            f"  - {v}" for v in violations
        )
        pytest.fail(msg)


if __name__ == "__main__":
    # Allow running this file directly to see current state
    file_dag = load_dag()
    domain_dag = build_domain_dag(file_dag)

    print(format_domain_dependencies(domain_dag))
    print()
    print(format_metrics(analyze_domain_metrics(domain_dag)))
    print()
    print(create_mermaid_diagram(domain_dag))
