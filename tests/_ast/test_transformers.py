from __future__ import annotations

import ast

from marimo._ast.transformers import NameTransformer


def test_name_transformer() -> None:
    # Test code
    code = """
def old_function():
    old_variable = 42
    return old_variable

class OldClass:
    def __init__(self):
        self.old_attribute = "hello"

old_global = "world"
    """

    # Create an AST from the code
    tree = ast.parse(code)

    # Define name substitutions
    name_substitutions = {
        "old_function": "new_function",
        "old_variable": "new_variable",
        "OldClass": "NewClass",
        "old_attribute": "new_attribute",
        "old_global": "new_global",
    }

    # Apply the NameTransformer
    transformer = NameTransformer(name_substitutions)
    new_tree = transformer.visit(tree)

    # Convert the new AST back to code
    new_code = ast.unparse(new_tree)

    # Expected transformed code
    expected_code = """
def new_function():
    old_variable = 42
    return old_variable

class NewClass:

    def __init__(self):
        self.old_attribute = 'hello'
new_global = 'world'
"""

    # Remove leading/trailing whitespace and normalize line endings
    new_code = new_code.strip()
    expected_code = expected_code.strip()

    # Assert that the transformation was successful
    assert new_code == expected_code
    assert transformer.made_changes


def test_name_transformer_no_changes() -> None:
    code = "x = 1"
    tree = ast.parse(code)
    transformer = NameTransformer({"y": "z"})
    new_tree = transformer.visit(tree)
    new_code = ast.unparse(new_tree)

    assert new_code.strip() == code.strip()
    assert not transformer.made_changes