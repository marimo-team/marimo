# Copyright 2025 Marimo. All rights reserved.

from marimo._lint.linter import contents_differ_excluding_generated_with


def test_contents_differ_excluding_generated_with():
    """Test that __generated_with differences are ignored in content comparison."""

    # Test case 1: Only __generated_with differs
    original = """import marimo

__generated_with = "0.8.0"
app = marimo.App()

@app.cell
def test():
    return

if __name__ == "__main__":
    app.run()
"""

    generated = """import marimo

__generated_with = "0.9.0"
app = marimo.App()

@app.cell
def test():
    return

if __name__ == "__main__":
    app.run()
"""

    # Should return False (no meaningful differences)
    assert not contents_differ_excluding_generated_with(original, generated)


def test_contents_differ_with_real_changes():
    """Test that real code differences are detected."""

    original = """import marimo

__generated_with = "0.8.0"
app = marimo.App()

@app.cell
def test():
    x = 1
    return

if __name__ == "__main__":
    app.run()
"""

    generated = """import marimo

__generated_with = "0.9.0"
app = marimo.App()

@app.cell
def test():
    x = 2  # Changed value
    return

if __name__ == "__main__":
    app.run()
"""

    # Should return True (real differences exist)
    assert contents_differ_excluding_generated_with(original, generated)


def test_contents_no_generated_with():
    """Test comparison when no __generated_with line exists."""

    original = """import marimo

app = marimo.App()

@app.cell
def test():
    return
"""

    generated = """import marimo

app = marimo.App()

@app.cell
def test():
    return
"""

    # Should return False (identical content)
    assert not contents_differ_excluding_generated_with(original, generated)


def test_contents_mixed_generated_with():
    """Test when only one file has __generated_with."""

    original = """import marimo

app = marimo.App()

@app.cell
def test():
    return
"""

    generated = """import marimo

__generated_with = "0.9.0"
app = marimo.App()

@app.cell
def test():
    return
"""

    # Should return True (one has __generated_with, one doesn't)
    assert contents_differ_excluding_generated_with(original, generated)
