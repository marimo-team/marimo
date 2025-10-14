"""
Pytest plugin that uses `ruff analyze graph` to discover and run tests
affected by changes from a git reference.

Usage:
    pytest --changed-from=HEAD
    pytest --changed-from=main
    pytest --changed-from=origin/main
"""

import json
import subprocess
from pathlib import Path

import pytest

print_ = print


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add command-line options for the plugin."""
    group = parser.getgroup(
        "ruff-graph", "Run tests based on dependency graph"
    )
    group.addoption(
        "--changed-from",
        action="store",
        dest="changed_from",
        default=None,
        help="Git reference to compare against (e.g., HEAD, main, origin/main)",
    )
    group.addoption(
        "--include-unchanged",
        action="store",
        dest="include_unchanged",
        default=False,
        type=lambda x: x.lower() in ("true", "1", "yes"),
        help="Also run tests that haven't changed (in addition to affected tests)",
    )


def get_changed_files(ref: str, repo_root: Path) -> set[Path]:
    """
    Get list of changed Python files from git diff.

    Args:
        ref: Git reference to compare against
        repo_root: Root of the git repository

    Returns:
        Set of absolute paths to changed Python files
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", ref],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )

        changed_files: set[Path] = set()
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            file_path = repo_root / line
            if file_path.suffix == ".py" and file_path.exists():
                changed_files.add(file_path)

        return changed_files
    except subprocess.CalledProcessError as e:
        error_msg = f"Failed to get git diff from '{ref}': {e}"
        if e.stderr:
            error_msg += f"\nStderr: {e.stderr}"
        error_msg += (
            "\n\nTip: Make sure the reference exists. "
            "In CI, you may need to fetch history with 'fetch-depth: 0' "
            "in actions/checkout."
        )
        pytest.exit(error_msg, returncode=1)


def get_dependency_graph(
    repo_root: Path, direction: str = "dependents"
) -> dict[str, list[str]]:
    """
    Get dependency graph from ruff analyze graph.

    Args:
        repo_root: Root of the repository
        direction: Either "dependencies" or "dependents"

    Returns:
        Dictionary mapping file paths to list of related file paths
    """
    try:
        result = subprocess.run(
            [
                "uvx",
                # uv notes `analyze graph` is experimental,
                # so we fix the ruff version for now
                "ruff@0.13.2",
                "analyze",
                "graph",
                "--detect-string-imports",
                "--direction",
                direction,
                ".",
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse JSON output
        graph: dict[str, list[str]] = json.loads(result.stdout)

        # Convert to absolute paths
        absolute_graph = {}
        for file_path, dependencies in graph.items():
            abs_path = str(repo_root / file_path)
            abs_deps = [str(repo_root / dep) for dep in dependencies]
            absolute_graph[abs_path] = abs_deps

        return absolute_graph
    except subprocess.CalledProcessError as e:
        pytest.exit(f"Failed to run ruff analyze graph: {e}", returncode=1)
    except json.JSONDecodeError as e:
        pytest.exit(f"Failed to parse ruff output: {e}", returncode=1)


def find_affected_files(
    changed_files: set[Path],
    dependency_graph: dict[str, list[str]],
) -> set[Path]:
    """
    Find all files affected by changes using BFS graph traversal.
    Handles cycles and deduplication.

    Args:
        changed_files: Set of files that have changed
        dependency_graph: Map of file -> files that depend on it

    Returns:
        Set of all affected file paths (including changed files)
    """
    affected: set[Path] = set(changed_files)
    visited: set[str] = set()
    queue: list[Path] = list(changed_files)

    while queue:
        current = queue.pop(0)
        current_str = str(current)

        if current_str in visited:
            continue
        visited.add(current_str)

        # Find all files that depend on this file
        dependents = dependency_graph.get(current_str, [])
        for dependent in dependents:
            dependent_path = Path(dependent)
            if dependent_path not in affected:
                affected.add(dependent_path)
                queue.append(dependent_path)

    return affected


def find_test_files(affected_files: set[Path], repo_root: Path) -> set[Path]:
    """
    Filter affected files to only include test files.

    Args:
        affected_files: Set of all affected files
        repo_root: Root of the repository

    Returns:
        Set of test file paths
    """
    del repo_root
    test_files: set[Path] = set()

    for file_path in affected_files:
        # Check if it's a test file
        if file_path.exists() and (
            file_path.name.startswith("test_")
            or file_path.name.endswith("_test.py")
            or "tests" in file_path.parts
        ):
            test_files.add(file_path)

    return test_files


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with our plugin."""
    changed_from: str | None = config.getoption("changed_from")

    if changed_from is None:
        return

    # Get the repository root
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        repo_root = Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        pytest.exit("Not in a git repository", returncode=1)

    # Step 1: Find changed files
    changed_files = get_changed_files(changed_from, repo_root)

    if not changed_files:
        print_(f"No Python files changed from {changed_from}")
        config.option.changed_test_files = set()
        return

    print_(
        f"Found {len(changed_files)} changed Python files from {changed_from}"
    )
    for f in sorted(changed_files):
        print_(f"  - {f.relative_to(repo_root)}")

    # Step 2: Get dependency graph (dependents direction)
    print_("\nBuilding dependency graph...")
    dependency_graph = get_dependency_graph(repo_root, direction="dependents")

    # Step 3: Find all affected files (BFS with cycle detection)
    print_("Finding affected files...")
    affected_files = find_affected_files(changed_files, dependency_graph)
    print_(f"Found {len(affected_files)} affected files")

    # Step 4: Filter to test files
    test_files = find_test_files(affected_files, repo_root)

    if not test_files:
        print_(f"\nNo tests affected by changes from {changed_from}")
        config.option.changed_test_files = set()
        return

    print_(f"\nFound {len(test_files)} affected test files:")
    for test_file in sorted(test_files):
        print_(f"  - {test_file.relative_to(repo_root)}")

    # Store the test files in config for collection hook
    config.option.changed_test_files = test_files

    if test_files:
        # Convert to relative paths for cleaner output
        test_paths = [
            str(f.relative_to(repo_root)) for f in sorted(test_files)
        ]
        config.args[:] = test_paths


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Modify test collection to only include affected tests."""
    changed_from: str | None = config.getoption("changed_from")

    if changed_from is None:
        return

    changed_test_files: set[Path] = getattr(
        config.option, "changed_test_files", set()
    )

    if not changed_test_files:
        # No affected tests, skip all
        for item in items:
            item.add_marker(
                pytest.mark.skip(
                    reason=f"Not affected by changes from {changed_from}"
                )
            )
        return

    include_unchanged = config.getoption("include_unchanged")

    # Filter items to only those in affected test files
    selected: list[pytest.Item] = []
    deselected: list[pytest.Item] = []

    for item in items:
        test_file = Path(item.fspath)

        if test_file in changed_test_files:
            selected.append(item)
        elif include_unchanged:
            # Run all tests if include_unchanged is set
            selected.append(item)
        else:
            deselected.append(item)

    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected

    print_(f"\nRunning {len(selected)} tests from affected files")
    if deselected:
        print_(f"Skipped {len(deselected)} tests from unaffected files")
