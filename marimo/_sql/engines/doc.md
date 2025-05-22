# SQL Engine Architecture

marimo's SQL engine uses a class hierarchy to separate catalog (metadata discovery) and query operations (execution).

## Class Hierarchy

```mermaid
classDiagram
    BaseEngine <|-- EngineCatalog
    BaseEngine <|-- QueryEngine
    EngineCatalog <|-- SQLConnection
    QueryEngine <|-- SQLConnection

    class BaseEngine {
        <<abstract>>
        +source: str
        +dialect: str
        +is_compatible(var: Any): bool
    }

    class EngineCatalog {
        <<abstract>>
        +inference_config: InferenceConfig
        +get_default_database(): str
        +get_default_schema(): str
        +get_databases(): list[Database]
        +get_tables_in_schema(): list[DataTable]
        +get_table_details(): DataTable
    }

    class QueryEngine {
        <<abstract>>
        +execute(query: str): Any
        +sql_output_format(): SqlOutputType
    }

    class SQLConnection {
        Implements both catalog and query interfaces
    }
```

Examples of just the catalog operations:

- PyIceberg

Examples of just the query operations:

- PEP 249

Examples of both catalog and query operations:

- SQLAlchemy/SQLModel
- DuckDB
- Clickhouse
- Ibis
