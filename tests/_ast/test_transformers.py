from __future__ import annotations

import ast
import sys

import pytest

from marimo._ast.transformers import (
    ARG_PREFIX,
    BlockException,
    CacheExtractWithBlock,
    ContainedExtractWithBlock,
    DeprivateVisitor,
    ExtractWithBlock,
    MangleArguments,
    NameTransformer,
    RemoveImportTransformer,
    RemoveReturns,
    clean_to_modules,
    compiled_ast,
    strip_function,
)


@pytest.mark.skipif(
    sys.version_info < (3, 9), reason="Feature not supported in python 3.8"
)
def test_name_transformer() -> None:
    # Name transformer should naively remap all occurrences of names in an AST,
    # without taking scoping into account.
    #
    # It does not transform attributes.
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
    new_variable = 42
    return new_variable

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


@pytest.mark.skipif(
    sys.version_info < (3, 9), reason="Feature not supported in python 3.8"
)
def test_name_transformer_no_changes() -> None:
    code = "x = 1"
    tree = ast.parse(code)
    transformer = NameTransformer({"y": "z"})
    new_tree = transformer.visit(tree)
    new_code = ast.unparse(new_tree)

    assert new_code.strip() == code.strip()
    assert not transformer.made_changes


def test_import_transformer_strip() -> None:
    code = """
import thing.marimo # Only line that's reasonable.
import marimo
import thing as marimo
from thing.thing import marimo
from thing import m as marimo
    """

    stripped = RemoveImportTransformer("marimo").strip_imports(code)
    assert stripped == "import thing.marimo"


def test_remove_import_transformer_import_from() -> None:
    """Test RemoveImportTransformer with from import statements."""
    transformer = RemoveImportTransformer("bar")

    # Test removing specific import - should return None when all names are removed
    import_from_node = ast.ImportFrom(
        module="foo", names=[ast.alias(name="bar", asname=None)]
    )
    result = transformer.visit(import_from_node)
    assert result is None  # Should be removed

    # Test keeping other imports - should return the node with remaining names
    import_from_node = ast.ImportFrom(
        module="foo", names=[ast.alias(name="baz", asname=None)]
    )
    result = transformer.visit(import_from_node)
    assert result is not None
    assert len(result.names) == 1
    assert result.names[0].name == "baz"

    # Test with alias - should keep since alias is different
    import_from_node = ast.ImportFrom(
        module="foo", names=[ast.alias(name="bar", asname="baz")]
    )
    result = transformer.visit(import_from_node)
    assert result is not None  # Should keep since alias is different
    assert len(result.names) == 1
    assert result.names[0].asname == "baz"

    # Test removing by alias - should return None when alias matches
    import_from_node = ast.ImportFrom(
        module="foo", names=[ast.alias(name="baz", asname="bar")]
    )
    result = transformer.visit(import_from_node)
    assert result is None  # Should be removed since alias matches

    # Test multiple names - some removed, some kept
    import_from_node = ast.ImportFrom(
        module="foo",
        names=[
            ast.alias(name="bar", asname=None),  # Should be removed
            ast.alias(name="baz", asname=None),  # Should be kept
        ],
    )
    result = transformer.visit(import_from_node)
    assert result is not None
    assert len(result.names) == 1
    assert result.names[0].name == "baz"


def test_compiled_ast() -> None:
    """Test the compiled_ast function."""
    # Test with simple statements
    statements = [
        ast.Assign(
            targets=[ast.Name(id="x", ctx=ast.Store())],
            value=ast.Constant(value=42),
        ),
        ast.Expr(
            value=ast.Call(
                func=ast.Name(id="print", ctx=ast.Load()),
                args=[ast.Name(id="x", ctx=ast.Load())],
                keywords=[],
            )
        ),
    ]

    result = compiled_ast(statements)
    assert isinstance(result, ast.Module)
    assert len(result.body) == 2


def test_clean_to_modules() -> None:
    """Test the clean_to_modules function."""
    # Create a simple with block
    with_block = ast.With(
        items=[
            ast.withitem(
                context_expr=ast.Call(
                    func=ast.Name(id="open", ctx=ast.Load()),
                    args=[ast.Constant(value="test.txt")],
                    keywords=[],
                ),
                optional_vars=ast.Name(id="f", ctx=ast.Store()),
            )
        ],
        body=[
            ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="f", ctx=ast.Load()),
                        attr="read",
                        ctx=ast.Load(),
                    ),
                    args=[],
                    keywords=[],
                )
            )
        ],
    )

    pre_block = [
        ast.Assign(
            targets=[ast.Name(id="x", ctx=ast.Store())],
            value=ast.Constant(value=1),
        )
    ]

    pre_module, with_module = clean_to_modules(pre_block, with_block)

    assert isinstance(pre_module, ast.Module)
    assert isinstance(with_module, ast.Module)
    assert len(pre_module.body) == 2  # original + the assignment from with
    assert len(with_module.body) == 1  # the body of the with block


def test_clean_to_modules_no_optional_vars() -> None:
    """Test clean_to_modules with a with block that has no 'as' clause."""
    with_block = ast.With(
        items=[
            ast.withitem(
                context_expr=ast.Call(
                    func=ast.Name(id="open", ctx=ast.Load()),
                    args=[ast.Constant(value="test.txt")],
                    keywords=[],
                ),
                optional_vars=None,
            )
        ],
        body=[ast.Expr(value=ast.Constant(value="hello"))],
    )

    pre_block = []
    pre_module, with_module = clean_to_modules(pre_block, with_block)

    assert isinstance(pre_module, ast.Module)
    assert isinstance(with_module, ast.Module)
    assert len(pre_module.body) == 1  # the context expression as an Expr
    assert len(with_module.body) == 1


def test_strip_function() -> None:
    """Test the strip_function function."""

    def test_function(x: int, y: str) -> int:
        result = x + len(y)
        return result

    module = strip_function(test_function)
    assert isinstance(module, ast.Module)

    # The function should be stripped of returns and arguments mangled
    code = ast.unparse(module)
    assert f"{ARG_PREFIX}result = {ARG_PREFIX}x + len({ARG_PREFIX}y)" in code
    assert "return result" not in code
    assert f"{ARG_PREFIX}x" in code
    assert f"{ARG_PREFIX}y" in code


def test_mangle_arguments() -> None:
    """Test the MangleArguments transformer."""
    code = """
def test_func(x, y):
    result = x + y
    return result
"""
    tree = ast.parse(code)
    args = {"x", "y"}

    transformer = MangleArguments(args)
    result = transformer.visit(tree)

    code_result = ast.unparse(result)
    assert f"{ARG_PREFIX}x" in code_result
    assert f"{ARG_PREFIX}y" in code_result
    assert (
        "result" in code_result
    )  # Should not be mangled since it's not in args


def test_mangle_arguments_custom_prefix() -> None:
    """Test MangleArguments with custom prefix."""
    code = "x = 1"
    tree = ast.parse(code)
    args = {"x"}

    transformer = MangleArguments(args, prefix="custom_")
    result = transformer.visit(tree)

    code_result = ast.unparse(result)
    assert "custom_x" in code_result


def test_deprivate_visitor() -> None:
    """Test the DeprivateVisitor transformer."""
    # Test with mangled local names
    code = "_cell_123_private_var = 42"
    tree = ast.parse(code)

    transformer = DeprivateVisitor()
    result = transformer.visit(tree)

    code_result = ast.unparse(result)
    assert "_private_var" in code_result
    assert "_cell_123_private_var" not in code_result


def test_remove_returns() -> None:
    """Test the RemoveReturns transformer."""
    code = """
def test_func():
    x = 1
    return x
    y = 2
"""
    tree = ast.parse(code)

    transformer = RemoveReturns()
    result = transformer.visit(tree)

    code_result = ast.unparse(result)
    assert "return x" not in code_result
    assert (
        "x" in code_result
    )  # The value should still be there as an expression


def test_extract_with_block_simple() -> None:
    """Test ExtractWithBlock with a simple with statement."""
    code = """
x = 1
with open("file.txt") as f:
    content = f.read()
    print(content)
"""
    tree = ast.parse(code)

    extractor = ExtractWithBlock(line=3, allowed_types=(ast.With,))
    pre_module, with_module = extractor.generic_visit(tree.body)

    assert isinstance(pre_module, ast.Module)
    assert isinstance(with_module, ast.Module)

    pre_code = ast.unparse(pre_module)
    with_code = ast.unparse(with_module)

    assert "x = 1" in pre_code
    assert "f = open('file.txt')" in pre_code
    assert "content = f.read()" in with_code
    assert "print(content)" in with_code


def test_extract_with_block_nested() -> None:
    """Test ExtractWithBlock with nested structures."""
    code = """
if True:
    with open("file.txt") as f:
        content = f.read()
        print(content)
"""
    tree = ast.parse(code)

    extractor = ExtractWithBlock(line=3, allowed_types=(ast.With, ast.If))
    pre_module, with_module = extractor.generic_visit(tree.body)

    assert isinstance(pre_module, ast.Module)
    assert isinstance(with_module, ast.Module)


def test_extract_with_block_error_no_with() -> None:
    """Test ExtractWithBlock raises error when no with statement is found."""
    code = """
x = 1
y = 2
"""
    tree = ast.parse(code)

    extractor = ExtractWithBlock(line=2, allowed_types=(ast.With,))

    with pytest.raises(BlockException):
        extractor.generic_visit(tree.body)


def test_cache_extract_with_block() -> None:
    """Test CacheExtractWithBlock."""
    code = """
x = 1
with cache:
    result = expensive_function()
    print(result)
"""
    tree = ast.parse(code)

    extractor = CacheExtractWithBlock(line=3)
    pre_module, with_module = extractor.generic_visit(tree.body)

    assert isinstance(pre_module, ast.Module)
    assert isinstance(with_module, ast.Module)


def test_cache_extract_with_block_try_error() -> None:
    """Test CacheExtractWithBlock raises error when first statement is try."""
    code = """
with cache:
    try:
        result = expensive_function()
    except Exception:
        result = None
"""
    tree = ast.parse(code)

    extractor = CacheExtractWithBlock(line=2)

    with pytest.raises(
        BlockException, match="first statement cannot be a try block"
    ):
        extractor.generic_visit(tree.body)


def test_contained_extract_with_block() -> None:
    """Test ContainedExtractWithBlock with various container types."""
    # Test with function
    code = """
def test_func():
    with app.setup:
        x = 1
        y = 2
"""
    tree = ast.parse(code)

    extractor = ContainedExtractWithBlock(line=3)
    pre_module, with_module = extractor.generic_visit(tree.body)

    assert isinstance(pre_module, ast.Module)
    assert isinstance(with_module, ast.Module)

    # Test with class
    code = """
class TestClass:
    def __init__(self):
        with app.setup:
            self.x = 1
"""
    tree = ast.parse(code)

    extractor = ContainedExtractWithBlock(line=4)
    pre_module, with_module = extractor.generic_visit(tree.body)

    assert isinstance(pre_module, ast.Module)
    assert isinstance(with_module, ast.Module)


def test_extract_with_block_inline_with() -> None:
    """Test ExtractWithBlock with inline with statement."""
    code = """
with cache: x = 1  # All on one line
"""
    tree = ast.parse(code)

    extractor = ExtractWithBlock(line=2, allowed_types=(ast.With,))

    # This should actually work, not raise an exception
    pre_module, with_module = extractor.generic_visit(tree.body)
    assert isinstance(pre_module, ast.Module)
    assert isinstance(with_module, ast.Module)


def test_name_transformer_assign_targets() -> None:
    """Test NameTransformer with assignment targets."""
    code = """
old_var = 42
old_var, other_var = 1, 2
"""
    tree = ast.parse(code)

    transformer = NameTransformer({"old_var": "new_var"})
    result = transformer.visit(tree)

    code_result = ast.unparse(result)
    assert "new_var = 42" in code_result
    assert (
        "new_var, other_var" in code_result
    )  # AST unparses tuples with parentheses
    assert "old_var" not in code_result
    assert transformer.made_changes


def test_name_transformer_class_def() -> None:
    """Test NameTransformer with class definitions."""
    code = """
class OldClass:
    pass
"""
    tree = ast.parse(code)

    transformer = NameTransformer({"OldClass": "NewClass"})
    result = transformer.visit(tree)

    code_result = ast.unparse(result)
    assert "class NewClass:" in code_result
    assert "class OldClass:" not in code_result
    assert transformer.made_changes


def test_name_transformer_no_substitutions() -> None:
    """Test NameTransformer when no substitutions are made."""
    code = """
def func():
    x = 1
    return x
"""
    tree = ast.parse(code)

    transformer = NameTransformer({})
    result = transformer.visit(tree)

    code_result = ast.unparse(result)
    assert code_result.strip() == code.strip()
    assert not transformer.made_changes
