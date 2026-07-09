# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "polars",
# ]
# ///

import marimo

__generated_with = "0.23.13"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # 🏡 Search with AI — data table filter bar

    Smoke test for the **"Search with AI"** filter bar on `mo.ui.table`
    (feature flag `ai_table_filter`, on by default in dev).

    **How to try it**

    1. Type a natural-language prompt into the table's search box below.
    2. Click the ✨ **Search with AI** button (or press `⌘↵`).
    3. The prompt is translated into a structured filter you can edit inline;
       press `Escape` / the ✕ to return to plain search.

    Requires an AI model to be configured in marimo's settings.
    """)
    return


@app.cell(hide_code=True)
def _(dt, pl):
    _city_state = {
        "Austin": "TX",
        "Denver": "CO",
        "Seattle": "WA",
        "Portland": "OR",
        "San Francisco": "CA",
    }
    _city = [
        "Austin", "Denver", "Seattle", "Portland", "Austin", "Denver",
        "Seattle", "San Francisco", "Austin", "Denver", "Portland", "Seattle",
        "Austin", "San Francisco", "Denver", "Portland", "Seattle", "Austin",
        "San Francisco", "Denver", "Portland", "Austin", "Seattle", "Denver",
    ]  # fmt: skip
    _property_type = [
        "house", "condo", "house", "townhouse", "house", "condo",
        "house", "condo", "condo", "house", "condo", "house",
        "house", "condo", "townhouse", "house", "condo", "house",
        "condo", "townhouse", "house", "house", "condo", "house",
    ]  # fmt: skip

    homes = pl.DataFrame(
        {
            "address": [
                "101 Oak St",
                "202 Maple Ave",
                "303 Pine Rd",
                "404 Cedar Ln",
                "505 Birch Blvd",
                "606 Elm St",
                "707 Walnut Way",
                "808 Aspen Ct",
                "909 Spruce Dr",
                "111 Willow Pl",
                "212 Chestnut St",
                "313 Poplar Ave",
                "414 Sycamore Rd",
                "515 Magnolia Ln",
                "616 Dogwood Dr",
                "717 Redwood Blvd",
                "818 Cypress St",
                "919 Juniper Way",
                "121 Palm Ct",
                "232 Hickory Dr",
                "343 Alder Pl",
                "454 Beech St",
                "565 Fir Ave",
                "676 Holly Rd",
            ],  # fmt: skip
            "city": _city,
            "state": [_city_state[c] for c in _city],
            "property_type": _property_type,
            "status": [
                "for_sale",
                "for_sale",
                "sold",
                "pending",
                "for_sale",
                "sold",
                "for_sale",
                "pending",
                "for_sale",
                "sold",
                "for_sale",
                "for_sale",
                "pending",
                "for_sale",
                "sold",
                "for_sale",
                "for_sale",
                "pending",
                "for_sale",
                "for_sale",
                "sold",
                "for_sale",
                "pending",
                "for_sale",
            ],  # fmt: skip
            "price": [
                525000,
                410000,
                690000,
                480000,
                1850000,
                375000,
                2400000,
                1200000,
                615000,
                940000,
                350000,
                1650000,
                780000,
                2950000,
                560000,
                1450000,
                430000,
                3200000,
                899000,
                725000,
                505000,
                1975000,
                640000,
                1150000,
            ],  # fmt: skip
            "bedrooms": [
                3,
                2,
                4,
                3,
                5,
                1,
                5,
                2,
                3,
                4,
                1,
                4,
                3,
                3,
                3,
                4,
                2,
                6,
                2,
                3,
                3,
                5,
                2,
                4,
            ],  # fmt: skip
            "bathrooms": [
                2.0,
                1.0,
                2.5,
                2.0,
                3.5,
                1.0,
                4.0,
                2.0,
                2.5,
                3.0,
                1.0,
                3.0,
                2.0,
                2.5,
                2.0,
                3.5,
                1.5,
                4.5,
                2.0,
                2.5,
                2.0,
                3.5,
                2.0,
                2.5,
            ],  # fmt: skip
            "sqft": [
                1800,
                950,
                2400,
                1600,
                3200,
                720,
                3800,
                1400,
                1750,
                2600,
                680,
                2900,
                1900,
                1650,
                2000,
                3100,
                1100,
                4200,
                1300,
                2100,
                1850,
                3400,
                1500,
                2500,
            ],  # fmt: skip
            "year_built": [
                1998,
                2005,
                1975,
                2018,
                1992,
                1968,
                2001,
                2020,
                1985,
                1958,
                2015,
                1995,
                2008,
                1978,
                1965,
                2003,
                2012,
                1990,
                2019,
                1988,
                1972,
                1996,
                2010,
                1983,
            ],  # fmt: skip
            "lot_size_acres": [
                0.18,
                0.0,
                0.25,
                0.12,
                0.45,
                0.0,
                0.6,
                0.0,
                0.0,
                0.3,
                0.0,
                0.35,
                0.2,
                0.0,
                0.28,
                0.5,
                0.0,
                0.75,
                0.0,
                0.14,
                0.22,
                0.55,
                0.0,
                0.32,
            ],  # fmt: skip
            "hoa_fee": [
                0,
                320,
                0,
                150,
                0,
                280,
                0,
                450,
                120,
                0,
                260,
                0,
                0,
                520,
                140,
                0,
                300,
                0,
                380,
                130,
                0,
                0,
                340,
                0,
            ],  # fmt: skip
            "days_on_market": [
                12,
                45,
                88,
                7,
                30,
                120,
                65,
                22,
                15,
                95,
                40,
                58,
                9,
                75,
                110,
                33,
                50,
                18,
                27,
                62,
                140,
                41,
                20,
                70,
            ],  # fmt: skip
            "listed_date": [
                dt.date(2024, 3, 14),
                dt.date(2024, 5, 2),
                dt.date(2024, 1, 20),
                dt.date(2024, 7, 8),
                dt.date(2024, 6, 11),
                dt.date(2023, 11, 30),
                dt.date(2024, 4, 22),
                dt.date(2024, 8, 5),
                dt.date(2024, 2, 17),
                dt.date(2024, 1, 9),
                dt.date(2024, 6, 28),
                dt.date(2024, 5, 19),
                dt.date(2024, 9, 1),
                dt.date(2024, 3, 3),
                dt.date(2023, 12, 15),
                dt.date(2024, 7, 25),
                dt.date(2024, 6, 6),
                dt.date(2024, 10, 12),
                dt.date(2024, 8, 19),
                dt.date(2024, 4, 14),
                dt.date(2024, 2, 28),
                dt.date(2024, 6, 30),
                dt.date(2024, 9, 15),
                dt.date(2024, 5, 27),
            ],  # fmt: skip
            "has_pool": [
                False,
                False,
                False,
                False,
                True,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                True,
                False,
                False,
                False,
                False,
                True,
                False,
                False,
                False,
                True,
                False,
                True,
            ],  # fmt: skip
            "has_garage": [pt != "condo" for pt in _property_type],
        }
    )
    return (homes,)


@app.cell
def _(homes):
    homes
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 🔍 Suggested prompts

    Type one of these into the search box, then click ✨ **Search with AI**.
    The right column is the filter query the AI is expected to produce
    (you can also type it directly once the filter bar is open).

    | Natural-language prompt | Expected filter query |
    | --- | --- |
    | Homes built before 2000 under $2m | `year_built:<2000 AND price:<2000000` |
    | 3+ bedroom houses for sale with a pool | `bedrooms>=3 AND property_type:house AND has_pool:true AND status:for_sale` |
    | Condos in Austin or Denver | `property_type:condo AND (city:Austin OR city:Denver)` |
    | Listings over $1M on the market more than 60 days | `price>1000000 AND days_on_market>60` |
    | Pending or sold homes | `status:(pending,sold)` |
    | Homes listed since June 2024 with no HOA | `listed_date:>=2024-06-01 AND hoa_fee:0` |
    | Not sold, at least 2 bathrooms | `NOT status:sold AND bathrooms>=2` |
    | Big houses (3000+ sqft) in Texas | `sqft>=3000 AND state:TX` |

    **Grammar cheatsheet**

    | Syntax | Meaning |
    | --- | --- |
    | `city:Austin` | text contains |
    | `status:(pending,sold)` | multi-value (OR within list) |
    | `a:x b:y` / `a:x AND b:y` | AND |
    | `a:x OR b:y` | OR |
    | `NOT status:sold` | negation |
    | `price>=500000` | comparison (`=`, `!=`, `>`, `>=`, `<`, `<=`) |
    | `listed_date:>2024-06-01` | date comparison |
    | `(a OR b) AND c` | grouping |
    """)
    return


@app.cell
def _():
    import datetime as dt

    import marimo as mo
    import polars as pl

    return dt, mo, pl


if __name__ == "__main__":
    app.run()
