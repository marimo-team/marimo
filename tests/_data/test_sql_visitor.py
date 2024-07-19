from __future__ import annotations

import ast
from textwrap import dedent

from marimo._data.sql_visitor import SQLVisitor


def test_execute_with_string_literal():
    source_code = "db.execute('SELECT * FROM users')"
    tree = ast.parse(source_code)
    visitor = SQLVisitor()
    visitor.visit(tree)
    assert visitor.get_sqls() == ["SELECT * FROM users"]


def test_sql_with_string_literal():
    source_code = "db.sql('UPDATE users SET name = \\'Alice\\' WHERE id = 1')"
    tree = ast.parse(source_code)
    visitor = SQLVisitor()
    visitor.visit(tree)
    assert visitor.get_sqls() == [
        "UPDATE users SET name = 'Alice' WHERE id = 1"
    ]


def test_execute_with_f_string():
    source_code = 'db.execute(f"SELECT * FROM users WHERE name = {name}")'
    tree = ast.parse(source_code)
    visitor = SQLVisitor()
    visitor.visit(tree)
    assert visitor.get_sqls() == ["SELECT * FROM users WHERE name = '_'"]


def test_no_sql_calls():
    source_code = "print('Hello, world!')"
    tree = ast.parse(source_code)
    visitor = SQLVisitor()
    visitor.visit(tree)
    assert visitor.get_sqls() == []


def test_sql_with_multiple_arguments():
    source_code = (
        "db.sql('SELECT * FROM users', 'This should not be captured')"
    )
    tree = ast.parse(source_code)
    visitor = SQLVisitor()
    visitor.visit(tree)
    assert visitor.get_sqls() == ["SELECT * FROM users"]


def test_multiple_sql_calls():
    source_code = dedent("""
        a = db.sql('SELECT * FROM users', 'This should not be captured')
        b = db.sql('ALTER TABLE users ADD COLUMN name TEXT')
        c = db.sql('UPDATE users SET name = \\'Alice\\' WHERE id = 1')
        """)
    tree = ast.parse(source_code)
    visitor = SQLVisitor()
    visitor.visit(tree)
    assert visitor.get_sqls() == [
        "SELECT * FROM users",
        "ALTER TABLE users ADD COLUMN name TEXT",
        "UPDATE users SET name = 'Alice' WHERE id = 1",
    ]


def test_sql_with_variable():
    source_code = dedent("""
      var = f"SELECT * FROM users WHERE name = {name}"
      db.sql(var)
    """)
    tree = ast.parse(source_code)
    visitor = SQLVisitor()
    visitor.visit(tree)
    assert visitor.get_sqls() == []
