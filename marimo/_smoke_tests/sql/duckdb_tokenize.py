# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb",
#     "marimo",
# ]
# ///
# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.7.20"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    import duckdb
    import re
    return duckdb, mo, re


@app.cell
def __(mo):
    default_code = """
    CREATE TABLE
            -- This is a comment
            IF NOT EXISTS
            -- This is another comment
            table1 (id INT)
    """
    code = mo.ui.code_editor(language="sql", value=default_code.strip())
    code
    return code, default_code


@app.cell
def __(code, duckdb):
    statements = duckdb.extract_statements(code.value)
    print("Number of statements: " + str(len(statements)))

    print(duckdb.tokenize(code.value))
    return statements,


@app.cell
def __(code, find_created_tables):
    find_created_tables(code.value)
    return


@app.cell
def __(re):
    def find_created_tables(sql_statement: str) -> list[str]:
        """
        Find the tables created in a SQL statement.

        This function uses the DuckDB tokenizer to find the tables created
        in a SQL statement. It returns a list of the table names created
        in the statement.

        Args:
            sql_statement: The SQL statement to parse.

        Returns:
            A list of the table names created in the statement.
        """

        import duckdb

        def remove_comments(sql):
            # Function to replace comments with spaces, preserving newlines
            def replace_with_spaces(match):
                return " " * len(match.group())

            # Split the SQL into strings and non-strings
            parts = re.split(r'(\'(?:\'\'|[^\'])*\'|"(?:""|[^"])*")', sql)

            for i in range(0, len(parts), 2):
                # Remove single-line comments
                parts[i] = re.sub(
                    r"--.*$", replace_with_spaces, parts[i], flags=re.MULTILINE
                )

                # Remove multi-line comments
                parts[i] = re.sub(r"/\*[\s\S]*?\*/", replace_with_spaces, parts[i])

            # Join the parts back together
            return "".join(parts)

        sql_statement = remove_comments(sql_statement)

        tokens = duckdb.tokenize(sql_statement)
        created_tables: list[str] = []
        i = 0

        def token_str(i: int) -> str:
            token = tokens[i]
            start = token[0]
            end = len(sql_statement) - 1
            if i + 1 < len(tokens):
                end = tokens[i + 1][0]
            return sql_statement[start:end].strip()

        def keyword_token_str(i: int) -> str:
            return token_str(i).lower()

        def token_type(i: int) -> str:
            return tokens[i][1]

        while i < len(tokens):
            if (
                keyword_token_str(i) == "create"
                and token_type(i) == duckdb.token_type.keyword
            ):
                i += 1
                if i < len(tokens) and keyword_token_str(i) == "or":
                    i += 2  # Skip 'OR REPLACE'
                if i < len(tokens) and keyword_token_str(i) in (
                    "temporary",
                    "temp",
                ):
                    i += 1  # Skip 'TEMPORARY' or 'TEMP'
                if i < len(tokens) and keyword_token_str(i) == "table":
                    i += 1
                    if i < len(tokens) and keyword_token_str(i) == "if":
                        i += 3  # Skip 'IF NOT EXISTS'
                    if i < len(tokens):
                        created_tables.append(token_str(i))
            i += 1

        return created_tables
    return find_created_tables,


if __name__ == "__main__":
    app.run()
