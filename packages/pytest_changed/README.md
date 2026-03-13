# pytest-changed Plugin

A pytest plugin that uses `ruff analyze graph` to intelligently discover and run only the tests affected by code changes.

## Overview

This plugin analyzes your git changes and uses Ruff's dependency graph analysis to determine which tests need to be run. It performs a search through the dependency graph to find all files affected by your changes, then runs only the tests that could be impacted.

## Usage

**Run only tests affected by changes from main branch:**

```bash
pytest -p packages.pytest_changed --changed-from=main
```

**Using Hatch:**

```bash
hatch run +py=3.12 test:test -p packages.pytest_changed --changed-from=main tests/
```

### Compare Against Different References

```bash
# Compare against HEAD (staged changes)
pytest -p packages.pytest_changed --changed-from=HEAD

# Compare against origin/main
pytest -p packages.pytest_changed --changed-from=origin/main
```

### Preview What Would Be Run

Use `--collect-only` to see which tests would be selected without running them:

```bash
pytest -p packages.pytest_changed --changed-from=main --collect-only tests/
```

### Include Unchanged Tests

Run affected tests plus all other tests:

```bash
pytest -p packages.pytest_changed --changed-from=main --include-unchanged tests/
```

### Run Specific Test Directories

The plugin respects pytest's normal path filtering:

```bash
pytest -p packages.pytest_changed --changed-from=main tests/_runtime/
```

## How It Works

1. **Find Changes**: Uses `git diff --name-only <ref>` to find Python files that have changed
2. **Build Graph**: Runs `ruff analyze graph --direction dependents` to build a dependency graph
3. **Graph Traversal**: Performs BFS from changed files to find all affected files
4. **Filter Tests**: Identifies which affected files are test files
5. **Run Tests**: Only runs pytest on the affected test files

## Configuration Options

### Command Line Options

- `--changed-from=<ref>`: Git reference to compare against (required to activate plugin)
- `--include-unchanged`: Also run tests that haven't changed (optional)
