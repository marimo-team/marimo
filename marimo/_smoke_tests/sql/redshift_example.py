# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "pandas==2.2.3",
#     "polars[pyarrow]==1.30.0",
#     "redshift-connector[full]==2.1.7",
#     "sqlglot==26.23.0",
# ]
# ///

import marimo

__generated_with = "0.13.14"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import redshift_connector
    import os
    return mo, os, redshift_connector


@app.cell
def _(mo):
    mo.md(
        r"""
    # Connecting to Redshift via redshift_connector

    Steps:

    1. Make sure the instance is publicly accessible
    2. Check VPC/subnets is public traffic is allowed
    3. Navigate to redshift -> workgroup -> obtain connection details
    """
    )
    return


@app.cell
def _(os, redshift_connector):
    # IAM Connection
    conn = redshift_connector.connect(
        iam=True,
        host=os.environ["HOST"],
        database="dev",
        access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        secret_access_key=os.environ["AWS_SECRET_KEY"],
        port=5439,
        region="ap-southeast-1",
    )

    # Default connection
    # _conn = redshift_connector.connect(
    #     host="testwg.549569150818.ap-southeast-1.redshift-serverless.amazonaws.com",
    #     database="dev",
    #     user="admin",
    #     password="****",
    #     port=5439,
    # )

    cursor = conn.cursor()
    return conn, cursor


@app.cell
def _(cursor):
    cursor.execute("DROP TABLE IF EXISTS users;")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER IDENTITY(1,1) PRIMARY KEY,
        username VARCHAR(50) NOT NULL,
        email VARCHAR(100) NOT NULL,
        created_date DATE NOT NULL
    )
    DISTSTYLE AUTO
    SORTKEY (user_id);
    """)

    cursor.execute("""
    INSERT INTO users (username, email, created_date) VALUES
        ('john_doe', 'john.doe@email.com', '2024-01-15'),
        ('jane_smith', 'jane.smith@email.com', '2024-02-20'),
        ('mike_wilson', 'mike.wilson@email.com', '2024-03-10'),
        ('sarah_jones', 'sarah.jones@email.com', '2024-04-05'),
        ('alex_brown', 'alex.brown@email.com', '2024-05-12');
    """)
    return


@app.cell
def _(conn, mo):
    _df = mo.sql(
        f"""
        SHOW COLUMNS FROM TABLE dev.public.users;
        """,
        engine=conn
    )
    return


@app.function
def close_prepared_statements_sample():
    import ast

    x = """{'S': 'ERROR', 'C': '42P05', 'M': 'prepared statement "redshift_connector_statement_90026_2" already exists', 'F': '/opt/brazil-pkg-cache/packages/RedshiftPADB/RedshiftPADB-1.0.12895.0/AL2_aarch64/generic-flavor/src/src/pg/src/backend/commands/commands_prepare.c', 'L': '685', 'R': 'StorePreparedStatement'}"""

    message = ast.literal_eval(x)["M"]
    parts = message.split('"')

    # The part within the first pair of double quotes is usually at index 1
    if len(parts) > 1:
        extracted_message = parts[1]
        print(f"Extracted message: {extracted_message}")
    else:
        print("Could not find content within double quotes.")


@app.cell
def _(mo):
    mo.md(
        r"""
    ## Introspection

    get_tables() ->
    [
      "dev", "information_schema", "views", "VIEW", None, "", "", "","", ""
    ]

    1. catalog
    2. schema
    3. table_name
    4. table_type
    5. unknown
    6. unknown
    7. unknown
    8. unknown
    9. unknown
    10. unknown

    get_schemas() -> ["information_schema", "dev"]

    1. schema
    2. catalog

    get_columns() -> [
      "dev",
      "public",
      "users",
      "user_id",
      4,
      "int4",
      10,
      None,
      0,
      10,
      0,
      None,
      "\"identity\"(110900, 0, '1,1'::text)",
      4,
      None,
      10,
      1,
      "NO",
      None,
      None,
      None,
      None,
      "YES",
      "YES"
    ]

    1. catalog
    2. schema
    3. table_name
    4. column_name
    5. unknown
    6. data type
    7. unknown
    ...
    14. unknown

    get_primary_keys() -> [
      "dev",
      "public",
      "users",
      "user_id",
      1,
      "users_pkey"
    ]

    1. catalog
    2. schema
    3. table_name
    4. column_name
    5. key_sequence
    6. pk_name
    """
    )
    return


if __name__ == "__main__":
    app.run()
