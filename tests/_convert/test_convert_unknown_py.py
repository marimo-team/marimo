from marimo._convert.converters import MarimoConvert
from marimo._convert.unknown_python import convert_unknown_py_to_notebook_ir
from tests.mocks import snapshotter

snapshot_test = snapshotter(__file__)


class TestConvertUnknownPython:
    """Test conversion of unknown Python files to marimo notebooks."""

    def test_simple_script_no_main(self) -> None:
        """Test conversion of a simple script without main block."""
        source = '''"""A simple script."""

import math

def calculate_area(radius):
    return math.pi * radius ** 2

print(calculate_area(5))
'''
        ir = convert_unknown_py_to_notebook_ir(source)
        converted = MarimoConvert.from_ir(ir).to_py()
        snapshot_test("simple_script_no_main.py.txt", converted)

    def test_script_with_main_block(self) -> None:
        """Test conversion of a script with if __name__ == "__main__": block."""
        source = '''"""Script with main block."""

import sys
import argparse

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("name", help="Name to greet")
    return parser.parse_args()

def greet(name):
    print(f"Hello, {name}!")

if __name__ == "__main__":
    args = parse_args()
    greet(args.name)
    sys.exit(0)
'''
        ir = convert_unknown_py_to_notebook_ir(source)
        converted = MarimoConvert.from_ir(ir).to_py()
        snapshot_test("script_with_main_block.py.txt", converted)

    def test_script_no_header_with_main(self) -> None:
        """Test conversion of a script without docstring but with main block."""
        source = """import os

CONFIG_PATH = os.path.expanduser("~/.config/myapp")

def setup():
    os.makedirs(CONFIG_PATH, exist_ok=True)

if __name__ == "__main__":
    setup()
    print(f"Config directory created at {CONFIG_PATH}")
"""
        ir = convert_unknown_py_to_notebook_ir(source)
        converted = MarimoConvert.from_ir(ir).to_py()
        snapshot_test("no_header_with_main.py.txt", converted)

    def test_script_no_header_no_main(self) -> None:
        """Test conversion of a minimal script."""
        source = """x = 5
y = 10
print(x + y)
"""
        ir = convert_unknown_py_to_notebook_ir(source)
        converted = MarimoConvert.from_ir(ir).to_py()
        snapshot_test("minimal_script.py.txt", converted)

    def test_script_with_nested_indentation(self) -> None:
        """Test conversion preserves indentation in main block."""
        source = '''"""Script with complex indentation."""

class Calculator:
    def add(self, a, b):
        return a + b

if __name__ == "__main__":
    calc = Calculator()
    for i in range(3):
        for j in range(3):
            result = calc.add(i, j)
            print(f"{i} + {j} = {result}")
'''
        ir = convert_unknown_py_to_notebook_ir(source)
        converted = MarimoConvert.from_ir(ir).to_py()
        snapshot_test("nested_indentation.py.txt", converted)

    def test_empty_main_block(self) -> None:
        """Test conversion of script with empty main block."""
        source = '''"""Script with empty main."""

data = [1, 2, 3, 4, 5]

if __name__ == "__main__":
    pass
'''
        ir = convert_unknown_py_to_notebook_ir(source)
        converted = MarimoConvert.from_ir(ir).to_py()
        snapshot_test("empty_main_block.py.txt", converted)
