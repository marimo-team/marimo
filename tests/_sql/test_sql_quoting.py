# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._sql.sql_quoting import (
    parse_fully_qualified_table_name,
    quote_qualified_name,
    quote_sql_identifier,
)


class TestQuoteSqlIdentifier:
    @pytest.mark.parametrize(
        ("identifier", "dialect", "expected"),
        [
            # DuckDB / Redshift / Postgres (double-quote style)
            ("table", "duckdb", '"table"'),
            ("my table", "duckdb", '"my table"'),
            ("nested.namespace", "duckdb", '"nested.namespace"'),
            ('has"quotes', "duckdb", '"has""quotes"'),
            ('double""already', "duckdb", '"double""""already"'),
            ("", "duckdb", '""'),
            ("unicode_ñoño", "duckdb", '"unicode_ñoño"'),
            ("back`ticks", "duckdb", '"back`ticks"'),
            # Redshift uses same double-quote style
            ("table", "redshift", '"table"'),
            ("my table", "redshift", '"my table"'),
            ('has"quotes', "redshift", '"has""quotes"'),
            # PostgreSQL aliases
            ("table", "postgresql", '"table"'),
            ("table", "postgres", '"table"'),
            # ClickHouse / MySQL (backtick style)
            ("table", "clickhouse", "`table`"),
            ("my table", "clickhouse", "`my table`"),
            ("nested.namespace", "clickhouse", "`nested.namespace`"),
            ("has`backtick", "clickhouse", "`has``backtick`"),
            ("double``already", "clickhouse", "`double````already`"),
            ("", "clickhouse", "``"),
            ("unicode_ñoño", "clickhouse", "`unicode_ñoño`"),
            ('has"quotes', "clickhouse", '`has"quotes`'),
            # MySQL same as clickhouse
            ("table", "mysql", "`table`"),
            ("has`backtick", "mysql", "`has``backtick`"),
            # BigQuery uses backtick style
            ("table", "bigquery", "`table`"),
            ("my table", "bigquery", "`my table`"),
            ("has`backtick", "bigquery", "`has``backtick`"),
            # Unknown dialect returns unquoted
            ("table", "sqlite", "table"),
            ("my table", "unknown", "my table"),
        ],
    )
    def test_quote_identifier(
        self, identifier: str, dialect: str, expected: str
    ) -> None:
        assert quote_sql_identifier(identifier, dialect=dialect) == expected

    @pytest.mark.parametrize(
        "identifier",
        [
            "simple",
            "with spaces",
            "with.dots",
            'with"quotes',
            "with`backticks",
            "with'single'quotes",
            "mixed.dots and spaces",
            "slashes/and/paths",
        ],
    )
    def test_duckdb_roundtrip_safe(self, identifier: str) -> None:
        """Verify that quoting an identifier produces valid DuckDB syntax."""
        quoted = quote_sql_identifier(identifier, dialect="duckdb")
        # Must start and end with double quotes
        assert quoted.startswith('"')
        assert quoted.endswith('"')
        # Inner content should not have unescaped double quotes
        inner = quoted[1:-1]
        # After un-escaping "", we should get back the original
        assert inner.replace('""', '"') == identifier

    @pytest.mark.parametrize(
        "identifier",
        [
            "simple",
            "with spaces",
            "with.dots",
            "with`backticks",
            'with"quotes',
        ],
    )
    def test_clickhouse_roundtrip_safe(self, identifier: str) -> None:
        """Verify that quoting an identifier produces valid ClickHouse syntax."""
        quoted = quote_sql_identifier(identifier, dialect="clickhouse")
        assert quoted.startswith("`")
        assert quoted.endswith("`")
        inner = quoted[1:-1]
        assert inner.replace("``", "`") == identifier


class TestQuoteQualifiedName:
    @pytest.mark.parametrize(
        ("parts", "dialect", "expected"),
        [
            # Simple 3-part name
            (
                ("mydb", "public", "users"),
                "duckdb",
                '"mydb"."public"."users"',
            ),
            # Parts with special characters
            (
                ("my.db", "my schema", "my.table"),
                "duckdb",
                '"my.db"."my schema"."my.table"',
            ),
            # ClickHouse 2-part name
            (
                ("default", "events"),
                "clickhouse",
                "`default`.`events`",
            ),
            # Redshift 3-part name
            (
                ("catalog", "schema", "table"),
                "redshift",
                '"catalog"."schema"."table"',
            ),
            # Single part
            (
                ("just_table",),
                "duckdb",
                '"just_table"',
            ),
            # Parts with quotes in them
            (
                ('db"name', "schema", "table"),
                "duckdb",
                '"db""name"."schema"."table"',
            ),
            (
                ("db`name", "table"),
                "clickhouse",
                "`db``name`.`table`",
            ),
        ],
    )
    def test_quote_qualified_name(
        self, parts: tuple[str, ...], dialect: str, expected: str
    ) -> None:
        assert quote_qualified_name(*parts, dialect=dialect) == expected


class TestParseFullyQualifiedTableName:
    @pytest.mark.parametrize(
        ("fqn", "expected"),
        [
            # Simple unquoted
            ("db.schema.table", ("db", "schema", "table")),
            # All quoted
            ('"db"."schema"."table"', ("db", "schema", "table")),
            # Quoted with dots inside
            (
                '"my.db"."my.schema"."my.table"',
                ("my.db", "my.schema", "my.table"),
            ),
            # Quoted with spaces
            (
                '"my db"."my schema"."my table"',
                ("my db", "my schema", "my table"),
            ),
            # Quoted with escaped double quotes
            ('"my""db"."schema"."table"', ('my"db', "schema", "table")),
            # Mixed quoted and unquoted
            ('"my.db".public.users', ("my.db", "public", "users")),
            # All parts have special chars
            (
                '"db.with.dots"."schema with spaces"."table""quoted"',
                ("db.with.dots", "schema with spaces", 'table"quoted'),
            ),
        ],
    )
    def test_parse_valid(
        self, fqn: str, expected: tuple[str, str, str]
    ) -> None:
        assert parse_fully_qualified_table_name(fqn) == expected

    @pytest.mark.parametrize(
        "fqn",
        [
            "just_a_table",
            "two.parts",
            "four.parts.here.extra",
            "",
            '"single_quoted"',
            '"two"."parts"',
            # Malformed quoted FQNs: unterminated or stray quotes
            '"unterminated',
            '"db"."schema"."table',
            'db"."schema"."table"',
            '"db".schema"."table',
            'db.sch"ema.table',
        ],
    )
    def test_parse_invalid(self, fqn: str) -> None:
        with pytest.raises(
            ValueError, match="Invalid fully qualified table name"
        ):
            parse_fully_qualified_table_name(fqn)

    def test_roundtrip_with_quote_qualified_name(self) -> None:
        """quote_qualified_name output should be parseable by parse_fully_qualified_table_name."""
        db, schema, table = "my.db", "my schema", 'table"name'
        fqn = quote_qualified_name(db, schema, table, dialect="duckdb")
        parsed = parse_fully_qualified_table_name(fqn)
        assert parsed == (db, schema, table)
