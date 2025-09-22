# MF005: sql-parse-error

✨ **Formatting** ❌ Not Fixable

MF005: SQL parsing errors during dependency analysis.

## What it does

Captures SQL parsing error logs and creates diagnostics pointing to
problematic SQL statements in cells.

## Why is this bad?

SQL parsing failures can lead to:
- Incorrect dependency analysis for SQL-using cells
- Missing dataframe references in dependency graph
- Reduced effectiveness of reactive execution
- Potential runtime errors when SQL is executed

## Examples

**Triggered by:**
- Invalid SQL syntax in cell code
- Unsupported SQL dialects or extensions
- Complex SQL that exceeds parser capabilities

## References

- [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
- [SQL Support](https://docs.marimo.io/guides/sql/)

