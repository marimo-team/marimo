# Lint Rules

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

### 🚨 Breaking Rules

These errors prevent notebook execution.

| Code | Name | Description | Fixable |
|------|------|-------------|----------|
| [MB001](rules/unparsable_cells.md) | unparsable-cells | Cell contains unparsable code | ❌ |
| [MB002](rules/multiple_definitions.md) | multiple-definitions | Multiple cells define the same variable | ❌ |
| [MB003](rules/cycle_dependencies.md) | cycle-dependencies | Cells have circular dependencies | ❌ |
| [MB004](rules/setup_cell_dependencies.md) | setup-cell-dependencies | Setup cell cannot have dependencies | ❌ |
| [MB005](rules/invalid_syntax.md) | invalid-syntax | Cell contains code that throws a SyntaxError on compilation | ❌ |

### ⚠️ Runtime Rules

These issues may cause runtime problems.

| Code | Name | Description | Fixable |
|------|------|-------------|----------|
| [MR001](rules/self_import.md) | self-import | Importing a module with the same name as the file | ❌ |

### ✨ Formatting Rules

These are style and formatting issues.

| Code | Name | Description | Fixable |
|------|------|-------------|----------|
| [MF001](rules/general_formatting.md) | general-formatting | General formatting issues with the notebook format. | 🛠️ |
| [MF002](rules/parse_stdout.md) | parse-stdout | Parse captured stdout during notebook loading | ❌ |
| [MF003](rules/parse_stderr.md) | parse-stderr | Parse captured stderr during notebook loading | ❌ |
| [MF004](rules/empty_cells.md) | empty-cells | Empty cells that can be safely removed. | ⚠️ |
| [MF005](rules/sql_parse_error.md) | sql-parse-error | SQL parsing errors during dependency analysis | ❌ |
| [MF006](rules/misc_log_capture.md) | misc-log-capture | Miscellaneous log messages during processing | ❌ |
| [MF007](rules/markdown_dedent.md) | markdown-dedent | Markdown strings in mo.md() should be dedented. | 🛠️ |

## Legend

- 🛠️ = Automatically fixable with `marimo check --fix`
- ⚠️ = Fixable with `marimo check --fix --unsafe-fixes` (may change code behavior)
- ❌ = Not automatically fixable

## Configuration

Most lint rules are enabled by default. You can configure the linter behavior through marimo's configuration system.

## Related Documentation

- [Understanding Errors](../understanding_errors/index.md) - Detailed explanations of common marimo errors
- [CLI Reference](../../cli.md) - Complete CLI documentation including `marimo check`
