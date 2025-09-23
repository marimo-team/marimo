# MF006: misc-log-capture

✨ **Formatting** ❌ Not Fixable

MF006: Miscellaneous log messages during processing.

## What it does

Captures warning and error level log messages that aren't handled by
other specific log rules and creates diagnostics to surface them.

## Why is this bad?

Unhandled log messages may indicate:
- Unexpected issues during notebook processing
- Configuration problems
- Library warnings that affect execution
- Performance or resource issues

## Examples

**Triggered by:**
- General warnings from imported libraries
- Configuration issues
- Unexpected errors during processing

## References

- [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)

