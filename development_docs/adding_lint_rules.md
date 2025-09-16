# Adding Lint Rules to marimo

This guide explains how to add new lint rules to marimo's linting system.

## Overview

marimo's lint system helps users write better, more reliable notebooks by detecting various issues that could prevent notebooks from running correctly. The system is organized around three severity levels:

- **Breaking (MB)**: Errors that prevent notebook execution
- **Runtime (MR)**: Issues that may cause runtime problems
- **Formatting (MF)**: Style and formatting issues

## Rule Code Assignment

Rule codes follow a specific pattern: `M[severity][number]`

### Current Code Ranges

- **MB001-MB099**: Breaking rules
- **MR001-MR099**: Runtime rules
- **MF001-MF099**: Formatting rules

### Assigning New Codes

When adding a new rule:

1. **Determine severity**: Choose Breaking, Runtime, or Formatting based on impact
2. **Find next available code**: Check existing rules in the appropriate category
3. **Use sequential numbering**: MB005, MB006, etc.

**Example assignments**:
- MB001: unparsable-cells
- MB002: multiple-definitions
- MB003: cycle-dependencies
- MB004: setup-cell-dependencies
- MF001: general-formatting
- MF002: parse-stdout
- MF003: parse-stderr

## Step-by-Step Implementation

### 1. Create the Rule Class

Create your rule in the appropriate directory:
- Breaking rules: `marimo/_lint/rules/breaking/`
- Runtime rules: `marimo/_lint/rules/runtime/`
- Formatting rules: `marimo/_lint/rules/formatting/`

**Template for a new rule**:

```python
# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.base import LintRule

if TYPE_CHECKING:
    from marimo._lint.context import RuleContext


class YourNewRule(LintRule):
    """MB005: Brief description of what this rule checks.

    Detailed explanation of what this rule does and why it's important.
    This should explain the technical details of how the rule works.

    ## What it does

    Clear, concise explanation of what the rule detects.

    ## Why is this bad?

    Explanation of why this issue is problematic:
    - Impact on notebook execution
    - Potential for bugs or confusion
    - Effect on reproducibility

    ## Examples

    **Problematic:**
    ```python
    # Example of code that violates this rule
    bad_code = "example"
    ```

    **Solution:**
    ```python
    # Example of how to fix the violation
    good_code = "example"
    ```

    ## References

    - [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
    - [Relevant Guide](https://docs.marimo.io/guides/...)
    """

    code = "MB005"  # Your assigned code
    name = "your-rule-name"  # Kebab-case name
    description = "Brief description for rule listings"
    severity = Severity.BREAKING  # Or RUNTIME/FORMATTING
    fixable = False  # True if rule can auto-fix issues

    async def check(self, ctx: RuleContext) -> None:
        """Implement your rule logic here."""
        # Iterate through notebook cells
        for cell in ctx.notebook.cells:
            # Your detection logic here
            if self._detect_violation(cell):
                diagnostic = Diagnostic(
                    message="Description of the specific violation",
                    line=cell.lineno,
                    column=cell.col_offset + 1,
                    code=self.code,
                    name=self.name,
                    severity=self.severity,
                    fixable=self.fixable,
                )
                await ctx.add_diagnostic(diagnostic)

    def _detect_violation(self, cell) -> bool:
        """Helper method for detection logic."""
        # Implement your specific detection logic
        return False
```

### 2. Register the Rule

Add your rule to the appropriate `__init__.py` file:

**For Breaking rules** (`marimo/_lint/rules/breaking/__init__.py`):

```python
from marimo._lint.rules.breaking.your_file import YourNewRule

BREAKING_RULE_CODES: dict[str, type[LintRule]] = {
    "MB001": UnparsableRule,
    "MB002": MultipleDefinitionsRule,
    "MB003": CycleDependenciesRule,
    "MB004": SetupCellDependenciesRule,
    "MB005": YourNewRule,  # Add your rule here
}

__all__ = [
    # ... existing rules ...
    "YourNewRule",  # Add to exports
    "BREAKING_RULE_CODES",
]
```

### 3. Create Test Files

#### a) Create a test notebook file

Create `tests/_lint/test_files/your_rule_name.py`:

```python
import marimo

__generated_with = "0.15.2"
app = marimo.App()


@app.cell
def _():
    # Code that should trigger your rule
    problematic_code = "example"
    return


@app.cell
def _():
    # Additional test cases
    return


if __name__ == "__main__":
    app.run()
```

#### b) Add snapshot test

Add to `tests/_lint/test_runtime_errors_snapshot.py`:

```python
def test_your_rule_snapshot():
    """Test snapshot for your new rule."""
    file = "tests/_lint/test_files/your_rule_name.py"
    with open(file) as f:
        code = f.read()

    notebook = parse_notebook(code, filepath=file)
    errors = lint_notebook(notebook)

    # Format errors for snapshot
    error_output = []
    for error in errors:
        error_output.append(error.format())

    snapshot("your_rule_name_errors.txt", "\n".join(error_output))
```

#### c) Add unit tests (optional but recommended)

For more rigorous testing, create `tests/_lint/test_your_rule.py`:

```python
import pytest
from marimo._ast.parse import parse_notebook
from marimo._lint.context import LintContext
from marimo._lint.rules.breaking import YourNewRule


class TestYourNewRule:
    """Test cases for YourNewRule."""

    async def test_detects_violation(self):
        """Test that the rule detects violations correctly."""
        code = """import marimo
app = marimo.App()

@app.cell
def _():
    # Code that should trigger the rule
    return
"""
        notebook = parse_notebook(code)
        ctx = LintContext(notebook)

        rule = YourNewRule()
        await rule.check(ctx)

        diagnostics = await ctx.get_diagnostics()
        assert len(diagnostics) > 0
        assert diagnostics[0].code == "MB005"
        assert diagnostics[0].severity == Severity.BREAKING

    async def test_no_false_positives(self):
        """Test that the rule doesn't trigger on valid code."""
        code = """import marimo
app = marimo.App()

@app.cell
def _():
    # Valid code that should not trigger the rule
    return
"""
        notebook = parse_notebook(code)
        ctx = LintContext(notebook)

        rule = YourNewRule()
        await rule.check(ctx)

        diagnostics = await ctx.get_diagnostics()
        assert len(diagnostics) == 0
```

### 4. Generate Documentation

The documentation is automatically generated from your rule's docstring. Run:

```bash
uv run scripts/generate_lint_docs.py
```

This will create:
- `docs/guides/lint_rules/rules/your_rule_name.md`
- Updated `docs/guides/lint_rules/index.md`

### 5. Run Tests

```bash
# Run lint tests
uv run hatch run test:test tests/_lint

# Run your specific test
uv run hatch run test:test tests/_lint/test_your_rule.py

# Update snapshots if needed
uv run hatch run test:test tests/_lint/test_runtime_errors_snapshot.py --snapshot-update
```

## Rule Implementation Guidelines

### Detection Logic

- **Prefer AST analysis** over string matching when possible
- **Use context information** from `RuleContext` (notebook, graph, etc.)
- **Be specific** in error messages - help users understand the exact issue
- **Consider edge cases** - test with various code patterns

### Error Messages

- **Be descriptive**: Explain what the issue is
- **Be actionable**: Suggest how to fix it
- **Be consistent**: Follow patterns from existing rules

Good: `"Variable 'x' is defined in multiple cells"`
Bad: `"Multiple definition error"`

### Performance

- **Avoid expensive operations** in the hot path
- **Cache results** when checking multiple cells (add to context if needed)
- **Early return** when possible

### Fixability

TODO: Right now, the only fixable errors are via re-serialization.

## Common Patterns

### Checking All Cells

```python
async def check(self, ctx: RuleContext) -> None:
    for cell in ctx.notebook.cells:
        if self._check_cell(cell):
            # Create diagnostic
```

### Using the Dependency Graph

```python
async def check(self, ctx: RuleContext) -> None:
    graph = ctx.get_graph()
    for cell_id, cell_data in graph.cells.items():
        # Analyze dependencies
```

## Testing Best Practices

### Snapshot Tests

- **Include in snapshot tests** for regression protection
- **Use realistic examples** that demonstrate the rule clearly
- **Test edge cases** in separate unit tests

### Unit Tests

- **Test positive cases** (rule triggers correctly)
- **Test negative cases** (no false positives)
- **Test edge cases** (empty cells, syntax errors, etc.)
- **Test multiple violations** in one notebook

### Test File Structure

```
tests/_lint/
├── test_files/           # Test notebooks
│   └── your_rule_name.py
├── snapshots/            # Expected outputs
│   └── your_rule_name_errors.txt
├── test_your_rule.py     # Unit tests
└── test_runtime_errors_snapshot.py  # Snapshot tests
```

## Documentation Requirements

Your rule's docstring should include:

1. **Rule code and brief description** in the first line
2. **## What it does** - Technical explanation
3. **## Why is this bad?** - Impact explanation
4. **## Examples** - Code samples (problematic and fixed)
5. **## References** - Links to relevant documentation

The documentation system will automatically:
- Generate individual rule pages
- Update the main rules index
- Create proper navigation links
- Use human-readable filenames

## Review Checklist

Before submitting your rule:

- [ ] Rule code follows numbering convention
- [ ] Rule is registered in appropriate `__init__.py`
- [ ] Comprehensive docstring with all required sections
- [ ] Unit tests cover positive and negative cases
- [ ] Snapshot test included
- [ ] Documentation generates correctly
- [ ] All lint tests pass
- [ ] Error messages are clear and actionable
- [ ] Performance is reasonable for large notebooks

## Example: Simple Rule Implementation

Here's a complete example of a simple rule that checks for syntax errors: https://github.com/marimo-team/marimo/pull/6384
