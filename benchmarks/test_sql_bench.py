# Copyright 2026 Marimo. All rights reserved.
"""Benchmarks for SQL cell analysis.

SQL cells participate in the reactive graph, which means every SQL statement
is tokenized and analyzed for the tables it defines and references.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._ast.sql_visitor import find_sql_defs, find_sql_refs

if TYPE_CHECKING:
    from pytest_codspeed import BenchmarkFixture

CREATE_STATEMENT = """
CREATE OR REPLACE TABLE analytics.daily_summary AS
SELECT
    date_trunc('day', events.created_at) AS day,
    users.country,
    count(*) AS event_count,
    sum(events.amount) AS total_amount
FROM raw.events AS events
JOIN raw.users AS users ON users.id = events.user_id
LEFT JOIN reference.countries AS countries ON countries.code = users.country
WHERE events.created_at >= '2024-01-01'
GROUP BY 1, 2
HAVING count(*) > 10
ORDER BY total_amount DESC;
"""

SELECT_STATEMENT = """
WITH recent AS (
    SELECT * FROM warehouse.orders WHERE created_at > now() - INTERVAL 30 DAY
),
enriched AS (
    SELECT recent.*, customers.segment
    FROM recent
    JOIN crm.customers AS customers ON customers.id = recent.customer_id
)
SELECT
    enriched.segment,
    count(*) FILTER (WHERE enriched.status = 'shipped') AS shipped,
    avg(enriched.total) AS average_total
FROM enriched
LEFT JOIN inventory.items AS items ON items.sku = enriched.sku
GROUP BY enriched.segment
ORDER BY average_total DESC
LIMIT 100;
"""


def test_find_sql_defs(benchmark: BenchmarkFixture) -> None:
    benchmark(find_sql_defs, CREATE_STATEMENT)


def test_find_sql_refs(benchmark: BenchmarkFixture) -> None:
    benchmark(find_sql_refs, SELECT_STATEMENT)
