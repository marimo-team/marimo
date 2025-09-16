# MB005: invalid-syntax

🚨 **Breaking** ❌ Not Fixable

MB005: Cell contains code that throws a SyntaxError on compilation.

## What it does

Attempts to compile each cell using marimo's internal compiler and catches any
SyntaxError exceptions that occur during the compilation process.

## Why is this bad?

Cells with syntax errors cannot be executed, making the notebook non-functional.
SyntaxErrors prevent marimo from creating the dependency graph and running the
reactive execution system, breaking the core functionality of the notebook.

## Examples

**Problematic:**
```python
# Invalid indentation
if True:
print("Hello")  # Missing indentation
```

**Problematic:**
```python
# Invalid syntax
x = 1 +  # Missing operand
```

**Problematic:**
```python
# Mismatched brackets
my_list = [1, 2, 3  # Missing closing bracket
```

**Solution:**
```python
# Fix indentation
if True:
    print("Hello")  # Proper indentation
```

**Solution:**
```python
# Complete expressions
x = 1 + 2  # Complete arithmetic expression
```

**Solution:**
```python
# Match brackets
my_list = [1, 2, 3]  # Proper closing bracket
```

## References

- [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
- [Python SyntaxError Documentation](https://docs.python.org/3/tutorial/errors.html#syntax-errors)

