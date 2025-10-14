# Copyright 2024 Marimo. All rights reserved.
"""
Snapshot tests for circular dependencies.

This test detects and tracks all circular dependencies in the codebase.
It helps prevent new cycles from being introduced and makes existing
cycles explicit.
"""

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import pytest
from inline_snapshot import snapshot


def load_dag() -> dict[str, list[str]]:
    """Load the DAG from the JSON file at the repo root."""
    dag_path = Path(__file__).parent.parent.parent / "dag.json"
    if not dag_path.exists():
        pytest.skip("dag.json not found - run: uvx ruff@0.13.2 analyze graph --direction dependents --detect-string-imports > dag.json")

    with open(dag_path) as f:
        return json.load(f)


def find_all_cycles(dag: dict[str, list[str]]) -> list[list[str]]:
    """
    Find all cycles in the dependency graph using Johnson's algorithm.

    Returns a list of cycles, where each cycle is a list of file paths.
    """
    # Build adjacency list
    graph: dict[str, set[str]] = defaultdict(set)
    for node, deps in dag.items():
        graph[node].update(deps)

    all_nodes = set(dag.keys())
    for deps in dag.values():
        all_nodes.update(deps)

    cycles: list[list[str]] = []

    def dfs(node: str, path: list[str], visited: set[str], rec_stack: set[str]) -> None:
        """DFS to find cycles."""
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                dfs(neighbor, path, visited, rec_stack)
            elif neighbor in rec_stack:
                # Found a cycle
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                # Normalize cycle (start from smallest node for consistent ordering)
                min_idx = cycle.index(min(cycle[:-1]))
                normalized = cycle[min_idx:-1] + cycle[:min_idx] + [cycle[min_idx]]
                if normalized not in cycles:
                    cycles.append(normalized)

        path.pop()
        rec_stack.remove(node)

    # Find all cycles
    visited: set[str] = set()
    for node in sorted(all_nodes):
        if node not in visited:
            dfs(node, [], visited, set())

    return sorted(cycles)


def find_strongly_connected_components(dag: dict[str, list[str]]) -> list[set[str]]:
    """
    Find strongly connected components (SCCs) using Tarjan's algorithm.

    Each SCC represents a group of files that are mutually dependent.
    """
    graph: dict[str, set[str]] = defaultdict(set)
    for node, deps in dag.items():
        graph[node].update(deps)

    all_nodes = set(dag.keys())
    for deps in dag.values():
        all_nodes.update(deps)

    index_counter = [0]
    stack: list[str] = []
    lowlinks: dict[str, int] = {}
    index: dict[str, int] = {}
    on_stack: set[str] = set()
    sccs: list[set[str]] = []

    def strongconnect(node: str) -> None:
        index[node] = index_counter[0]
        lowlinks[node] = index_counter[0]
        index_counter[0] += 1
        stack.append(node)
        on_stack.add(node)

        for neighbor in graph.get(node, []):
            if neighbor not in index:
                strongconnect(neighbor)
                lowlinks[node] = min(lowlinks[node], lowlinks[neighbor])
            elif neighbor in on_stack:
                lowlinks[node] = min(lowlinks[node], index[neighbor])

        if lowlinks[node] == index[node]:
            scc: set[str] = set()
            while True:
                w = stack.pop()
                on_stack.remove(w)
                scc.add(w)
                if w == node:
                    break
            if len(scc) > 1:  # Only include non-trivial SCCs
                sccs.append(scc)

    for node in sorted(all_nodes):
        if node not in index:
            strongconnect(node)

    return sorted(sccs, key=lambda s: (-len(s), sorted(s)))


def extract_domain(file_path: str) -> str | None:
    """Extract the domain (second-level folder) from a file path."""
    parts = Path(file_path).parts

    if len(parts) < 2:
        return None

    if parts[0] == "marimo":
        if len(parts) == 2:
            return parts[1].replace(".py", "")
        return parts[1]

    if parts[0] == "tests":
        if len(parts) == 2:
            return "tests"
        return f"tests/{parts[1]}"

    return parts[0]


def find_domain_cycles(dag: dict[str, list[str]]) -> list[list[str]]:
    """Find cycles at the domain level."""
    # Build domain graph
    domain_graph: dict[str, set[str]] = defaultdict(set)

    for file_path, dependencies in dag.items():
        source_domain = extract_domain(file_path)
        if source_domain is None:
            continue

        for dep_path in dependencies:
            target_domain = extract_domain(dep_path)
            if target_domain is None or source_domain == target_domain:
                continue

            domain_graph[source_domain].add(target_domain)

    # Find cycles in domain graph
    cycles: list[list[str]] = []

    def dfs(node: str, path: list[str], visited: set[str], rec_stack: set[str]) -> None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in domain_graph.get(node, []):
            if neighbor not in visited:
                dfs(neighbor, path, visited, rec_stack)
            elif neighbor in rec_stack:
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                min_idx = cycle.index(min(cycle[:-1]))
                normalized = cycle[min_idx:-1] + cycle[:min_idx] + [cycle[min_idx]]
                if normalized not in cycles:
                    cycles.append(normalized)

        path.pop()
        rec_stack.remove(node)

    visited: set[str] = set()
    for node in sorted(domain_graph.keys()):
        if node not in visited:
            dfs(node, [], visited, set())

    return sorted(cycles)


def format_cycles(cycles: list[list[str]]) -> str:
    """Format cycles as a readable string."""
    if not cycles:
        return "# No cycles found! 🎉"

    lines = [
        f"# Circular Dependencies Found: {len(cycles)}",
        "",
        "Each cycle represents a group of files that depend on each other.",
        "Breaking these cycles improves maintainability and testability.",
        "",
    ]

    for i, cycle in enumerate(cycles, 1):
        lines.append(f"## Cycle {i} ({len(cycle) - 1} files)")
        lines.append("")
        for j, file_path in enumerate(cycle[:-1]):
            lines.append(f"  {file_path}")
            lines.append(f"    ↓")
        lines.append(f"  {cycle[-1]}")
        lines.append("")

    return "\n".join(lines)


def format_sccs(sccs: list[set[str]]) -> str:
    """Format strongly connected components as a readable string."""
    if not sccs:
        return "# No strongly connected components found! 🎉"

    lines = [
        f"# Strongly Connected Components: {len(sccs)}",
        "",
        "These are groups of files that are mutually dependent.",
        "Each SCC should ideally be refactored into separate layers.",
        "",
    ]

    for i, scc in enumerate(sccs, 1):
        lines.append(f"## SCC {i} ({len(scc)} files)")
        lines.append("")
        for file_path in sorted(scc):
            lines.append(f"  - {file_path}")
        lines.append("")

    return "\n".join(lines)


def format_domain_cycles(cycles: list[list[str]]) -> str:
    """Format domain-level cycles as a readable string."""
    if not cycles:
        return "# No domain-level cycles found! 🎉"

    lines = [
        f"# Domain-Level Circular Dependencies: {len(cycles)}",
        "",
        "These are high-level architectural cycles between major components.",
        "Domain cycles are especially concerning and should be prioritized for refactoring.",
        "",
    ]

    for i, cycle in enumerate(cycles, 1):
        lines.append(f"## Domain Cycle {i}")
        lines.append("")
        cycle_str = " → ".join(cycle)
        lines.append(f"  {cycle_str}")
        lines.append("")

    return "\n".join(lines)


def test_file_cycles_snapshot() -> None:
    """
    Snapshot test for file-level circular dependencies.

    This test will fail if new cycles are introduced or existing cycles change.
    """
    dag = load_dag()
    cycles = find_all_cycles(dag)

    output = format_cycles(cycles)
    assert output == snapshot()


def test_strongly_connected_components_snapshot() -> None:
    """
    Snapshot test for strongly connected components.

    SCCs represent groups of files that are mutually dependent.
    """
    dag = load_dag()
    sccs = find_strongly_connected_components(dag)

    output = format_sccs(sccs)
    assert output == snapshot()


def test_domain_cycles_snapshot() -> None:
    """
    Snapshot test for domain-level circular dependencies.

    This tracks architectural cycles between major components.
    """
    dag = load_dag()
    domain_cycles = find_domain_cycles(dag)

    output = format_domain_cycles(domain_cycles)
    assert output == snapshot()


def test_cycle_statistics_snapshot() -> None:
    """
    Snapshot test for overall cycle statistics.
    """
    dag = load_dag()
    file_cycles = find_all_cycles(dag)
    sccs = find_strongly_connected_components(dag)
    domain_cycles = find_domain_cycles(dag)

    # Calculate statistics
    total_files_in_cycles = len(set(f for cycle in file_cycles for f in cycle[:-1]))
    total_files = len(dag)

    lines = [
        "# Cycle Statistics",
        "",
        f"Total files: {total_files}",
        f"Files involved in cycles: {total_files_in_cycles}",
        f"Percentage of files in cycles: {total_files_in_cycles / total_files * 100:.1f}%",
        "",
        f"Total file-level cycles: {len(file_cycles)}",
        f"Total strongly connected components: {len(sccs)}",
        f"Total domain-level cycles: {len(domain_cycles)}",
        "",
        "## Largest Cycles",
        "",
    ]

    # Sort cycles by size
    sorted_cycles = sorted(file_cycles, key=lambda c: len(c), reverse=True)[:5]
    for i, cycle in enumerate(sorted_cycles, 1):
        lines.append(f"{i}. {len(cycle) - 1} files:")
        for file_path in cycle[:-1]:
            lines.append(f"   - {file_path}")
        lines.append("")

    output = "\n".join(lines)
    assert output == snapshot()


def test_no_new_cycles_in_core_domains() -> None:
    """
    Strict test: certain core domains should remain cycle-free.

    This test enforces that critical domains don't develop cycles.
    """
    dag = load_dag()
    domain_cycles = find_domain_cycles(dag)

    # Domains that should remain cycle-free
    cycle_free_domains = {"_config", "_utils"}

    violations = []
    for cycle in domain_cycles:
        for domain in cycle[:-1]:
            if domain in cycle_free_domains:
                violations.append(f"{domain} is in cycle: {' → '.join(cycle)}")

    if violations:
        msg = "Core domains should not have cycles:\n" + "\n".join(f"  - {v}" for v in violations)
        pytest.fail(msg)


if __name__ == "__main__":
    # Allow running this file directly to see current state
    dag = load_dag()

    print("=" * 80)
    print(format_domain_cycles(find_domain_cycles(dag)))
    print()
    print("=" * 80)
    print(format_cycles(find_all_cycles(dag)))
    print()
    print("=" * 80)
    print(format_sccs(find_strongly_connected_components(dag)))
