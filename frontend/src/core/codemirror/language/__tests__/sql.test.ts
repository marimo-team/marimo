/* Copyright 2024 Marimo. All rights reserved. */
import { expect, describe, it, afterEach, beforeEach } from "vitest";
import {
  SQLCompletionStore,
  SQLLanguageAdapter,
  type SQLLanguageAdapterMetadata,
} from "../languages/sql";
import { store } from "@/core/state/jotai";
import {
  dataSourceConnectionsAtom,
  DUCKDB_ENGINE,
  setLatestEngineSelected,
  type ConnectionName,
} from "@/core/datasets/data-source-connections";
import type { DataSourceConnection } from "@/core/kernel/messages";
import { PostgreSQL } from "@codemirror/lang-sql";
import { datasetsAtom } from "@/core/datasets/state";
import type { DatasetsState } from "@/core/datasets/types";

const adapter = new SQLLanguageAdapter();

describe("SQLLanguageAdapter", () => {
  describe("defaultMetadata", () => {
    it("should be set", () => {
      expect(adapter.defaultMetadata).toMatchInlineSnapshot(`
        {
          "commentLines": [],
          "dataframeName": "_df",
          "engine": "${DUCKDB_ENGINE}",
          "quotePrefix": "f",
          "showOutput": true,
        }
      `);
    });
  });

  describe("transformIn", () => {
    it("empty", () => {
      const [innerCode, offset, metadata] = adapter.transformIn("");
      expect(innerCode).toBe("");
      expect(offset).toBe(0);
      const out = adapter.transformOut(innerCode, metadata);
      expect(out).toMatchInlineSnapshot(`
        [
          "_df = mo.sql(
            f"""

            """
        )",
          24,
        ]
      `);
    });

    it("should extract inner SQL from triple double-quoted strings", () => {
      const pythonCode = '_df = mo.sql("""SELECT * FROM {df}""")';
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM {df}");
      expect(metadata.dataframeName).toBe("_df");
      expect(offset).toBe(16);
    });

    it("should handle single double-quoted strings", () => {
      const pythonCode = 'next_df = mo.sql("SELECT * FROM {df}")';
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM {df}");
      expect(metadata.dataframeName).toBe("next_df");
      expect(offset).toBe(18);
    });

    it("should handle triple single-quoted strings", () => {
      const pythonCode = "next_df = mo.sql('''SELECT * \nFROM {df}''')";
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * \nFROM {df}");
      expect(offset).toBe(20);
    });

    it("should return as is if not sql", () => {
      const pythonCode = 'next_df = print("Hello, World!")';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe('next_df = print("Hello, World!")');
      expect(offset).toBe(0);
    });

    it("should handle an empty string", () => {
      const pythonCode = 'next_df = mo.sql("")';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("");
      expect(offset).toBe(18);
    });

    it("simple sql", () => {
      const pythonCode = 'next_df = mo.sql("SELECT * FROM {df}")';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM {df}");
      expect(offset).toBe(18);
    });

    it("should trim strings with leading and trailing whitespace", () => {
      const pythonCode = 'next_df = mo.sql("""   \nSELECT * FROM {df}\n   """)';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM {df}");
      expect(offset).toBe(20);
    });

    it("should handle space around the f-strings", () => {
      const pythonCode = 'next_df = mo.sql(\n\t"""\nSELECT * FROM {df}\n"""\n)';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM {df}");
      expect(offset).toBe(22);
    });

    it("should handle output flag set to True", () => {
      const pythonCode = '_df = mo.sql("""SELECT * FROM table""", output=True)';
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM table");
      expect(metadata.showOutput).toBe(true);
      expect(offset).toBe(16);
    });

    it("should handle output flag set to False", () => {
      const pythonCode =
        '_df = mo.sql("""SELECT * FROM table""", output=False)';
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM table");
      expect(metadata.showOutput).toBe(false);
      expect(offset).toBe(16);

      // handle trailing comma
      const pythonCode2 =
        '_df = mo.sql("""SELECT * FROM table""", output=False,)';
      const [innerCode2, offset2, metadata2] = adapter.transformIn(pythonCode2);
      expect(innerCode2).toBe("SELECT * FROM table");
      expect(metadata2.showOutput).toBe(false);
      expect(offset2).toBe(16);
    });

    it("should default to showing output when flag is not specified", () => {
      const pythonCode = '_df = mo.sql("""SELECT * FROM table""")';
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM table");
      expect(metadata.showOutput).toBe(true);
      expect(offset).toBe(16);
    });

    it("should handle engine param when provided", () => {
      const pythonCode =
        '_df = mo.sql("""SELECT * FROM table""", engine=postgres_engine)';
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM table");
      expect(offset).toBe(16);
      expect(metadata.engine).toBe("postgres_engine");

      // handle trailing comma
      const pythonCode2 =
        '_df = mo.sql("""SELECT * FROM table""", engine=postgres_engine,)';
      const [innerCode2, offset2, metadata2] = adapter.transformIn(pythonCode2);
      expect(innerCode2).toBe("SELECT * FROM table");
      expect(offset2).toBe(16);
      expect(metadata2.engine).toBe("postgres_engine");
    });

    it("should handle engine param with output flag", () => {
      const pythonCode =
        '_df = mo.sql("""SELECT * FROM table""", output=False, engine=postgres_engine)';
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM table");
      expect(offset).toBe(16);
      expect(metadata.showOutput).toBe(false);
      expect(metadata.engine).toBe("postgres_engine");
    });

    it("should handle reversed order of params", () => {
      const pythonCode =
        '_df = mo.sql("""SELECT * FROM table""", engine=postgres_engine, output=False)';
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM table");
      expect(offset).toBe(16);
      expect(metadata.showOutput).toBe(false);
      expect(metadata.engine).toBe("postgres_engine");
    });

    it("should handle parametrized sql", () => {
      const pythonCode = `
_df = mo.sql(
    f"""
    SELECT name, price, category
    FROM products
    WHERE price < {price_threshold.value}
    ORDER BY price DESC
    """,
    engine=sqlite,
)
`;
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe(
        `
SELECT name, price, category
FROM products
WHERE price < {price_threshold.value}
ORDER BY price DESC
        `.trim(),
      );
      expect(offset).toBe(22);
      expect(metadata.showOutput).toBe(true);
      expect(metadata.engine).toBe("sqlite");
    });

    it("should handle parametrized sql with triple single quotes f-string", () => {
      const pythonCode = `
_df = mo.sql(
    f'''
    SELECT name, price, category
    FROM products
    WHERE price < {price_threshold.value}
    ORDER BY price DESC
    ''',
    engine=sqlite,
)
`;
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe(
        `
SELECT name, price, category
FROM products
WHERE price < {price_threshold.value}
ORDER BY price DESC
        `.trim(),
      );
      expect(offset).toBe(22);
      expect(metadata.engine).toBe("sqlite");
    });

    it("should handle parametrized sql with inline double quotes f-string", () => {
      const pythonCode = `
_df = mo.sql(
    f"FROM products WHERE price < {price_threshold.value}",
    engine=sqlite,
)
`;
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe(
        "FROM products WHERE price < {price_threshold.value}",
      );
      expect(offset).toBe(20);
      expect(metadata.engine).toBe("sqlite");
    });

    it("should handle parametrized sql with inline single quotes f-string", () => {
      const pythonCode = `
_df = mo.sql(
    f"FROM products WHERE price < {price_threshold.value}",
    engine=sqlite,
)
`;
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe(
        "FROM products WHERE price < {price_threshold.value}",
      );
      expect(offset).toBe(20);
      expect(metadata.engine).toBe("sqlite");
    });
  });

  describe("transformOut", () => {
    let metadata: SQLLanguageAdapterMetadata;

    beforeEach(() => {
      metadata = {
        engine: DUCKDB_ENGINE,
        showOutput: true,
        dataframeName: "_df",
        quotePrefix: "f",
        commentLines: [],
      };
    });

    it("should wrap SQL code with triple double-quoted string format", () => {
      const code = "SELECT * FROM {df}";
      metadata.quotePrefix = "f";
      metadata.dataframeName = "my_df";
      const [wrappedCode, offset] = adapter.transformOut(code, metadata);
      expect(wrappedCode).toMatchInlineSnapshot(`
        "my_df = mo.sql(
            f"""
            SELECT * FROM {df}
            """
        )"
      `);
      expect(offset).toBe(26);
    });

    it("should include output flag when set to False", () => {
      const code = "SELECT * FROM table";
      metadata.quotePrefix = "f";
      metadata.dataframeName = "my_df";
      metadata.showOutput = false;
      const [wrappedCode, offset] = adapter.transformOut(code, metadata);
      expect(wrappedCode).toMatchInlineSnapshot(`
        "my_df = mo.sql(
            f"""
            SELECT * FROM table
            """,
            output=False
        )"
      `);
      expect(offset).toBe(26);
    });

    it("should not include output flag when set to True", () => {
      const code = "SELECT * FROM table";
      metadata.quotePrefix = "f";
      metadata.dataframeName = "my_df";
      metadata.showOutput = true;
      const [wrappedCode, offset] = adapter.transformOut(code, metadata);
      expect(wrappedCode).toMatchInlineSnapshot(`
        "my_df = mo.sql(
            f"""
            SELECT * FROM table
            """
        )"
      `);
      expect(offset).toBe(26);
    });

    it("should preserve Python comments", () => {
      const pythonCode = '# hello\nmy_df = mo.sql("""SELECT * FROM {df}""")';
      const [innerCode, , metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM {df}");
      const [wrappedCode, offset] = adapter.transformOut(innerCode, metadata);
      expect(wrappedCode).toMatchInlineSnapshot(`
        "# hello
        my_df = mo.sql(
            f"""
            SELECT * FROM {df}
            """
        )"
      `);
      expect(offset).toBe(26);
    });

    it("should add engine connection when provided", () => {
      const code = "SELECT * FROM table";
      metadata.engine = "postgres_engine" as ConnectionName;
      metadata.commentLines = ["# hello"];
      const [wrappedCode, offset] = adapter.transformOut(code, metadata);
      expect(wrappedCode).toMatchInlineSnapshot(`
        "# hello
        _df = mo.sql(
            f"""
            SELECT * FROM table
            """,
            engine=postgres_engine
        )"
      `);
      expect(offset).toBe(24);
    });

    it("should add engine connection and output flag when provided", () => {
      const code = "SELECT * FROM table";
      metadata.showOutput = false;
      metadata.engine = "postgres_engine" as ConnectionName;
      metadata.commentLines = ["# hello"];
      const [wrappedCode, offset] = adapter.transformOut(code, metadata);
      expect(wrappedCode).toMatchInlineSnapshot(`
        "# hello
        _df = mo.sql(
            f"""
            SELECT * FROM table
            """,
            output=False,
            engine=postgres_engine
        )"
      `);
      expect(offset).toBe(24);
    });
  });

  describe("isSupported", () => {
    it("should return true for supported sql string formats", () => {
      expect(
        adapter.isSupported('df2 = mo.sql("""SELECT * FROM {df}""")'),
      ).toBe(true);
      expect(adapter.isSupported("my_df = mo.sql('')")).toBe(true);
      expect(adapter.isSupported('df = mo.sql("")')).toBe(true);
      expect(adapter.isSupported('# this is a sql cell\ndf = mo.sql("")')).toBe(
        true,
      );
      expect(
        adapter.isSupported(
          '# this is a sql cell\n# with multiple comments\ndf = mo.sql("")',
        ),
      ).toBe(true);
      expect(adapter.isSupported(new SQLLanguageAdapter().defaultCode)).toBe(
        true,
      );
    });

    it("should return false for unsupported string formats", () => {
      expect(adapter.isSupported('print("Hello, World!")')).toBe(false);
      expect(adapter.isSupported("mo.sql()")).toBe(false);
      expect(adapter.isSupported("mo.sql('')")).toBe(false);
      expect(adapter.isSupported('mo.sql("")')).toBe(false);
      expect(adapter.isSupported("_df = mo.sql()")).toBe(false);
      expect(adapter.isSupported('df := mo.sql("")')).toBe(false);
    });

    it("should return false sequences that look like sql but are not", () => {
      const once = 'df = mo.sql("""SELECT * FROM {df}""")';
      const pythonCode = [once, once].join("\n");
      expect(adapter.isSupported(pythonCode)).toBe(false);
    });

    it("should return false when there are multiple sql strings", () => {
      const pythonCode = `
      _df = mo.sql("""SELECT * FROM table1""")
      _df2 = mo.sql("""SELECT * FROM table2""")
      `;
      expect(adapter.isSupported(pythonCode)).toBe(false);
    });

    it("should return false when there are non sql strings with sql string", () => {
      const pythonCode = `print("Hello, World!") \n_df = mo.sql("SELECT * FROM table")`;
      expect(adapter.isSupported(pythonCode)).toBe(false);

      const pythonCode2 = `_df = mo.sql("""SELECT * FROM table""") \n print("Hello, World!")`;
      expect(adapter.isSupported(pythonCode2)).toBe(false);
    });

    it("should return true for sql strings with whitespace before or after", () => {
      expect(
        adapter.isSupported(' df = mo.sql("""SELECT * FROM table""")'),
      ).toBe(true);
      expect(
        adapter.isSupported('df = mo.sql("""SELECT * FROM table""") '),
      ).toBe(true);
    });

    it("should support SQL strings with output flag", () => {
      expect(
        adapter.isSupported(
          'df = mo.sql("""SELECT * FROM table""", output=True)',
        ),
      ).toBe(true);
      expect(
        adapter.isSupported(
          'df = mo.sql("""SELECT * FROM table""", output=False)',
        ),
      ).toBe(true);
    });

    it("should support SQL strings with output flag multi-line", () => {
      expect(
        adapter.isSupported(
          `
        countries = mo.sql(
            f"""
            SELECT * from "https://raw.githubusercontent.com/data.csv"
            """,
            output=False
        )`.trim(),
        ),
      ).toBe(true);
      expect(
        adapter.isSupported(
          `
        countries = mo.sql(
            f"""
            SELECT * from "https://raw.githubusercontent.com/data.csv"
            """,
            output=False,
        )`.trim(),
        ),
      ).toBe(true);
      expect(
        adapter.isSupported(
          `
        countries = mo.sql(
            f"""
            SELECT * from "https://raw.githubusercontent.com/data.csv"
            """,
            output=False)`.trim(),
        ),
      ).toBe(true);
    });
  });

  describe("latestEngineSelected", () => {
    afterEach(() => {
      const state = store.get(dataSourceConnectionsAtom);
      const connections = new Map(state.connectionsMap);
      connections
        .set("postgres_engine" as ConnectionName, {
          name: "postgres_engine" as ConnectionName,
          source: "postgres",
          display_name: "PostgreSQL",
          dialect: "postgres",
          databases: [],
        })
        .set("mysql_engine" as ConnectionName, {
          name: "mysql_engine" as ConnectionName,
          source: "mysql",
          display_name: "MySQL",
          dialect: "mysql",
          databases: [],
        })
        .set(DUCKDB_ENGINE, {
          name: DUCKDB_ENGINE,
          source: "duckdb",
          display_name: "DuckDB",
          dialect: "duckdb",
          databases: [],
        });
      store.set(dataSourceConnectionsAtom, {
        ...state,
        connectionsMap: connections,
      });
    });

    const getLatestEngine = () =>
      store.get(dataSourceConnectionsAtom).latestEngineSelected;

    it("should use default engine initially", () => {
      expect(getLatestEngine()).toBe(DUCKDB_ENGINE);
    });

    it("should persist the selected engine", () => {
      const engine = "mysql_engine" as ConnectionName;
      setLatestEngineSelected(engine);
      expect(getLatestEngine()).toBe(engine);

      setLatestEngineSelected("postgres_engine" as ConnectionName);
      expect(getLatestEngine()).toBe("postgres_engine");
    });

    it("should not change when engine is not in connectionsMap", () => {
      const engine = "unknown_engine" as ConnectionName;
      setLatestEngineSelected(engine);
      expect(getLatestEngine()).not.toBe("unknown_engine");
    });

    it("should update engine in transformIn when specified", () => {
      const pythonCode = '_df = mo.sql("""SELECT 1""", engine=postgres_engine)';
      const metadata = adapter.transformIn(pythonCode)[2];
      expect(metadata.engine).toBe("postgres_engine");
      expect(getLatestEngine()).toBe("postgres_engine");

      // Don't update for unspecified engine
      const pythonCode2 = '_df = mo.sql("""SELECT 1""")';
      const metadata2 = adapter.transformIn(pythonCode2)[2];
      expect(metadata2.engine).toBe(DUCKDB_ENGINE);
      expect(getLatestEngine()).toBe("postgres_engine");

      // Don't update for unknown engine
      const pythonCode3 = '_df = mo.sql("""SELECT 1""", engine=unknown_engine)';
      const metadata3 = adapter.transformIn(pythonCode3)[2];
      expect(metadata3.engine).toBe("unknown_engine");
      expect(getLatestEngine()).toBe("postgres_engine");
    });

    it("should maintain engine selection across transformIn/transformOut", () => {
      const engine = "postgres_engine" as ConnectionName;
      setLatestEngineSelected(engine);

      const [innerCode, , metadata] = adapter.transformIn(
        `_df = mo.sql("""SELECT 1""", engine=${engine})`,
      );
      expect(metadata.engine).toBe(engine);

      const [outCode] = adapter.transformOut(innerCode, metadata);
      expect(outCode).toContain(`engine=${engine}`);
    });

    it("should maintain engine when transforming empty string", () => {
      const engine = "postgres_engine" as ConnectionName;
      setLatestEngineSelected(engine);

      const [innerCode, , metadata] = adapter.transformIn("");
      expect(metadata.engine).toBe(engine);

      const [outCode] = adapter.transformOut(innerCode, metadata);
      expect(outCode).toContain(`engine=${engine}`);
    });

    it("should restore previous engine when selecting default", () => {
      const engine = "postgres_engine" as ConnectionName;
      setLatestEngineSelected(engine);
      setLatestEngineSelected(DUCKDB_ENGINE);

      expect(getLatestEngine()).toBe(DUCKDB_ENGINE);
    });
  });

  describe("defaultCode", () => {
    it("should include engine in defaultCode when selected", () => {
      const engine = "postgres_engine" as ConnectionName;
      setLatestEngineSelected(engine);
      expect(adapter.defaultCode).toBe(
        `_df = mo.sql(f"""SELECT * FROM """, engine=${engine})`,
      );
    });

    it("should not include engine in defaultCode when using default engine", () => {
      setLatestEngineSelected(DUCKDB_ENGINE);
      expect(adapter.defaultCode).toBe(`_df = mo.sql(f"""SELECT * FROM """)`);
    });
  });
});

describe("tablesCompletionSource", () => {
  const mockStore = store;
  const completionStore = new SQLCompletionStore();

  beforeEach(() => {
    // Reset the adapter engine
    setLatestEngineSelected(DUCKDB_ENGINE);
    // reset the datasets state
    mockStore.set(datasetsAtom, {
      tables: [],
    } as unknown as DatasetsState);

    // reset the dataSourceConnectionsAtom
    mockStore.set(dataSourceConnectionsAtom, {
      connectionsMap: new Map(),
      latestEngineSelected: DUCKDB_ENGINE,
    });
  });

  it("should return null if connection not found", () => {
    mockStore.set(dataSourceConnectionsAtom, {
      connectionsMap: new Map(),
      latestEngineSelected: DUCKDB_ENGINE,
    });

    const completionSource = completionStore.getCompletionSource(
      "test_engine" as ConnectionName,
    );
    expect(completionSource).toBe(null);
  });

  it("should create schema with schema.table structure", () => {
    const mockConnection: DataSourceConnection = {
      name: "test_engine",
      dialect: "duckdb",
      display_name: "duckdb",
      source: "duckdb",
      databases: [
        {
          dialect: "duckdb",
          name: "test_db",
          schemas: [
            {
              name: "public",
              tables: [
                {
                  name: "users",
                  source: "duckdb",
                  source_type: "local",
                  type: "table",
                  columns: [
                    {
                      name: "id",
                      external_type: "string",
                      type: "string",
                      sample_values: [],
                    },
                    {
                      name: "name",
                      external_type: "string",
                      type: "string",
                      sample_values: [],
                    },
                    {
                      name: "email",
                      external_type: "string",
                      type: "string",
                      sample_values: [],
                    },
                  ],
                },
                {
                  name: "orders",
                  source: "duckdb",
                  source_type: "local",
                  type: "table",
                  columns: [
                    {
                      name: "order_id",
                      external_type: "string",
                      type: "string",
                      sample_values: [],
                    },
                    {
                      name: "user_id",
                      external_type: "string",
                      type: "string",
                      sample_values: [],
                    },
                    {
                      name: "total",
                      external_type: "number",
                      type: "number",
                      sample_values: [],
                    },
                  ],
                },
              ],
            },
          ],
        },
      ],
    };

    mockStore.set(dataSourceConnectionsAtom, {
      connectionsMap: new Map([
        ["test_engine" as ConnectionName, mockConnection],
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ]) as any,
      latestEngineSelected: "test_engine" as ConnectionName,
    });

    const completionSource = completionStore.getCompletionSource(
      "test_engine" as ConnectionName,
    );
    expect(completionSource?.defaultTable).toBeUndefined();
    expect(completionSource?.dialect).toBe(undefined);
    expect(completionSource?.schema).toMatchInlineSnapshot(`
      {
        "public": {
          "orders": [
            "order_id",
            "user_id",
            "total",
          ],
          "users": [
            "id",
            "name",
            "email",
          ],
        },
      }
    `);
  });

  it("should handle multiple databases and schemas", () => {
    const mockConnection: DataSourceConnection = {
      name: "multi_db_engine",
      dialect: "postgres",
      display_name: "postgres",
      source: "postgres",
      databases: [
        {
          name: "db1",
          dialect: "postgres",
          schemas: [
            {
              name: "schema1",
              tables: [
                {
                  name: "table1",
                  source: "postgres",
                  source_type: "local",
                  type: "table",
                  columns: [
                    {
                      name: "col1",
                      external_type: "string",
                      type: "string",
                      sample_values: [],
                    },
                  ],
                },
              ],
            },
          ],
        },
        {
          name: "db2",
          dialect: "postgres",
          schemas: [
            {
              name: "schema2",
              tables: [
                {
                  name: "table2",
                  source: "postgres",
                  source_type: "local",
                  type: "table",
                  columns: [
                    {
                      name: "col2",
                      external_type: "string",
                      type: "string",
                      sample_values: [],
                    },
                  ],
                },
              ],
            },
          ],
        },
      ],
    };

    mockStore.set(dataSourceConnectionsAtom, {
      connectionsMap: new Map([
        [mockConnection.name as ConnectionName, mockConnection],
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ]) as any,
      latestEngineSelected: mockConnection.name as ConnectionName,
    });

    const completionSource = completionStore.getCompletionSource(
      "multi_db_engine" as ConnectionName,
    );
    // expect fully qualified 'database.schema.table' names
    // as there is no default database
    expect(completionSource?.schema).toMatchInlineSnapshot(`
      {
        "db1": {
          "schema1": {
            "table1": [
              "col1",
            ],
          },
        },
        "db2": {
          "schema2": {
            "table2": [
              "col2",
            ],
          },
        },
      }
    `);
    expect(completionSource?.defaultTable).toBeUndefined();
  });

  it("should handle multiple databases and schemas with default", () => {
    const mockConnection: DataSourceConnection = {
      name: "multi_db_engine",
      dialect: "postgres",
      display_name: "postgres",
      source: "postgres",
      default_schema: "schema2",
      default_database: "db1",
      databases: [
        {
          name: "db1",
          dialect: "postgres",
          schemas: [
            {
              name: "schema1",
              tables: [
                {
                  name: "table1",
                  source: "postgres",
                  source_type: "local",
                  type: "table",
                  columns: [
                    {
                      name: "col1",
                      external_type: "string",
                      type: "string",
                      sample_values: [],
                    },
                  ],
                },
              ],
            },
            {
              name: "schema2",
              tables: [
                {
                  name: "table2",
                  source: "postgres",
                  source_type: "local",
                  type: "table",
                  columns: [
                    {
                      name: "col2",
                      external_type: "string",
                      type: "string",
                      sample_values: [],
                    },
                  ],
                },
              ],
            },
          ],
        },
        {
          name: "db2",
          dialect: "postgres",
          schemas: [
            {
              name: "schema2",
              tables: [
                {
                  name: "table2",
                  source: "postgres",
                  source_type: "local",
                  type: "table",
                  columns: [
                    {
                      name: "col2",
                      external_type: "string",
                      type: "string",
                      sample_values: [],
                    },
                  ],
                },
              ],
            },
          ],
        },
        {
          name: "db3",
          dialect: "postgres",
          schemas: [
            {
              name: "schema2",
              tables: [
                {
                  name: "table2",
                  source: "postgres",
                  source_type: "local",
                  type: "table",
                  columns: [
                    {
                      name: "col2",
                      external_type: "string",
                      type: "string",
                      sample_values: [],
                    },
                  ],
                },
              ],
            },
          ],
        },
      ],
    };

    mockStore.set(dataSourceConnectionsAtom, {
      connectionsMap: new Map([
        [mockConnection.name as ConnectionName, mockConnection],
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ]) as any,
      latestEngineSelected: mockConnection.name as ConnectionName,
    });

    const completionSource = completionStore.getCompletionSource(
      "multi_db_engine" as ConnectionName,
    );
    expect(completionSource?.schema).toMatchInlineSnapshot(`
      {
        "db2": {
          "schema2": {
            "table2": [
              "col2",
            ],
          },
        },
        "db3": {
          "schema2": {
            "table2": [
              "col2",
            ],
          },
        },
        "schema1": {
          "table1": [
            "col1",
          ],
        },
        "schema2": {
          "table2": [
            "col2",
          ],
        },
      }
    `);
    expect(completionSource?.defaultTable).toBeUndefined();
    expect(completionSource?.defaultSchema).toBe("schema2");
  });

  it("should handle default schema", () => {
    const mockConnection: DataSourceConnection = {
      name: "test_engine",
      dialect: "postgres",
      display_name: "postgres",
      source: "postgres",
      default_schema: "public",
      default_database: "test_db",
      databases: [
        {
          name: "test_db",
          dialect: "postgres",
          schemas: [
            {
              name: "public",
              tables: [
                {
                  name: "users",
                  source: "postgres",
                  source_type: "local",
                  type: "table",
                  columns: [
                    {
                      name: "id",
                      external_type: "string",
                      type: "string",
                      sample_values: [],
                    },
                    {
                      name: "name",
                      external_type: "string",
                      type: "string",
                      sample_values: [],
                    },
                    {
                      name: "email",
                      external_type: "string",
                      type: "string",
                      sample_values: [],
                    },
                  ],
                },
              ],
            },
          ],
        },
      ],
    };

    mockStore.set(dataSourceConnectionsAtom, {
      connectionsMap: new Map([
        [mockConnection.name as ConnectionName, mockConnection],
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ]) as any,
      latestEngineSelected: mockConnection.name as ConnectionName,
    });

    const completionSource = completionStore.getCompletionSource(
      "test_engine" as ConnectionName,
    );
    expect(completionSource?.schema).toMatchInlineSnapshot(`
      {
        "public": {
          "users": [
            "id",
            "name",
            "email",
          ],
        },
      }
    `);
    expect(completionSource?.defaultTable).toBe("users");
    expect(completionSource?.defaultSchema).toBe("public");
  });

  it("should create a default table if there is only one table", () => {
    const mockConnection: DataSourceConnection = {
      name: "test_engine",
      dialect: "postgres",
      display_name: "postgres",
      source: "postgres",
      databases: [
        {
          name: "test_db",
          dialect: "postgres",
          schemas: [
            {
              name: "public",
              tables: [
                {
                  name: "users",
                  source: "postgres",
                  source_type: "local",
                  type: "table",
                  columns: [],
                },
              ],
            },
          ],
        },
      ],
    };

    mockStore.set(dataSourceConnectionsAtom, {
      connectionsMap: new Map([
        [mockConnection.name as ConnectionName, mockConnection],
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ]) as any,
      latestEngineSelected: mockConnection.name as ConnectionName,
    });

    const completionSource = completionStore.getCompletionSource(
      "test_engine" as ConnectionName,
    );
    expect(completionSource?.defaultTable).toBe("users");
    expect(completionSource?.dialect).toBe(PostgreSQL);
  });

  it("should handle schemaless databases", () => {
    const mockConnection: DataSourceConnection = {
      name: "test_engine",
      dialect: "postgres",
      display_name: "postgres",
      default_database: "test_db",
      source: "postgres",
      databases: [
        {
          name: "test_db",
          dialect: "postgres",
          schemas: [
            {
              name: "", // lack of name indicates schemaless
              tables: [
                {
                  name: "users",
                  source: "postgres",
                  source_type: "local",
                  type: "table",
                  columns: [
                    {
                      name: "id",
                      external_type: "string",
                      type: "string",
                      sample_values: [],
                    },
                  ],
                },
              ],
            },
          ],
        },
        {
          name: "test_db2",
          dialect: "postgres",
          schemas: [
            {
              name: "",
              tables: [
                {
                  name: "orders",
                  source: "postgres",
                  source_type: "local",
                  type: "table",
                  columns: [
                    {
                      name: "order_id",
                      external_type: "string",
                      type: "string",
                      sample_values: [],
                    },
                  ],
                },
              ],
            },
          ],
        },
      ],
    };

    mockStore.set(dataSourceConnectionsAtom, {
      connectionsMap: new Map([
        [mockConnection.name as ConnectionName, mockConnection],
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ]) as any,
      latestEngineSelected: mockConnection.name as ConnectionName,
    });

    const completionSource = completionStore.getCompletionSource(
      "test_engine" as ConnectionName,
    );
    expect(completionSource?.defaultTable).toBe(undefined);
    expect(completionSource?.dialect).toBe(PostgreSQL);
    expect(completionSource?.schema).toMatchInlineSnapshot(`
      {
        "test_db2": {
          "orders": [
            "order_id",
          ],
        },
        "users": [
          "id",
        ],
      }
      `);
  });

  it("should return local tables", () => {
    const testDatasets = [
      {
        name: "dataset1",
        columns: [
          { name: "col1", type: "number" },
          { name: "col2", type: "string" },
        ],
      },
    ];
    mockStore.set(datasetsAtom, { tables: testDatasets } as DatasetsState);

    const mockConnection: DataSourceConnection = {
      name: "test_engine",
      dialect: "duckdb",
      display_name: "duckdb",
      default_database: "test_db",
      default_schema: "test_schema",
      source: "duckdb",
      databases: [
        {
          dialect: "duckdb",
          name: "test_db",
          schemas: [
            {
              name: "test_schema",
              tables: [
                {
                  name: "dataset2",
                  source: "duckdb",
                  source_type: "local",
                  type: "table",
                  columns: [
                    {
                      name: "col1",
                      external_type: "string",
                      type: "string",
                      sample_values: [],
                    },
                  ],
                },
              ],
            },
          ],
        },
      ],
    };
    mockStore.set(dataSourceConnectionsAtom, {
      connectionsMap: new Map([
        ["test_engine" as ConnectionName, mockConnection],
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ]) as any,
      latestEngineSelected: "test_engine" as ConnectionName,
    });

    const completionSource = completionStore.getCompletionSource(
      "test_engine" as ConnectionName,
    );
    expect(completionSource?.schema).toMatchInlineSnapshot(`
      {
        "dataset1": [
          "col1",
          "col2",
        ],
        "test_schema": {
          "dataset2": [
            "col1",
          ],
        },
      }
    `);
  });

  it("should return new connection tables when connection is updated", () => {
    mockStore.set(dataSourceConnectionsAtom, {
      connectionsMap: new Map([
        ["test_engine" as ConnectionName, mockConnection],
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ]) as any,
      latestEngineSelected: "test_engine" as ConnectionName,
    });

    const completionSource = completionStore.getCompletionSource(
      "test_engine" as ConnectionName,
    );
    expect(completionSource?.schema).toMatchInlineSnapshot(`
    {
      "test_schema": {
        "dataset2": [
          "col1",
        ],
      },
    }
    `);

    const newConnection: DataSourceConnection = {
      ...mockConnection,
      default_schema: "new_schema",
    };

    mockStore.set(dataSourceConnectionsAtom, {
      ...mockStore.get(dataSourceConnectionsAtom),
      connectionsMap: new Map([
        ["test_engine" as ConnectionName, newConnection],
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ]) as any,
      latestEngineSelected: "test_engine" as ConnectionName,
    });

    const completionSource2 = completionStore.getCompletionSource(
      "test_engine" as ConnectionName,
    );
    expect(completionSource2?.defaultSchema).toBe("new_schema");
  });

  it("should return new local tables when local tables are updated", () => {
    mockStore.set(dataSourceConnectionsAtom, {
      connectionsMap: new Map([
        ["test_engine" as ConnectionName, mockConnection],
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ]) as any,
      latestEngineSelected: "test_engine" as ConnectionName,
    });
    mockStore.set(datasetsAtom, { tables: testDatasets } as DatasetsState);
    const completionSource = completionStore.getCompletionSource(
      "test_engine" as ConnectionName,
    );
    expect(completionSource?.schema).toMatchInlineSnapshot(`
    {
      "dataset1": [
        "col1",
        "col2",
      ],
      "test_schema": {
        "dataset2": [
          "col1",
        ],
      },
    }
    `);

    const newTestDatasets = [
      {
        name: "dataset3",
        columns: [
          { name: "col1", type: "number" },
          { name: "col2", type: "string" },
        ],
      },
    ];
    mockStore.set(datasetsAtom, { tables: newTestDatasets } as DatasetsState);

    const newCompletionSource = completionStore.getCompletionSource(
      "test_engine" as ConnectionName,
    );
    expect(newCompletionSource?.schema).toMatchInlineSnapshot(`
    {
      "dataset3": [
        "col1",
        "col2",
      ],
      "test_schema": {
        "dataset2": [
          "col1",
        ],
      },
    }
    `);
  });
});

const mockConnection: DataSourceConnection = {
  name: "test_engine",
  dialect: "duckdb",
  display_name: "duckdb",
  default_database: "test_db",
  default_schema: "test_schema",
  source: "duckdb",
  databases: [
    {
      dialect: "duckdb",
      name: "test_db",
      schemas: [
        {
          name: "test_schema",
          tables: [
            {
              name: "dataset2",
              source: "duckdb",
              source_type: "local",
              type: "table",
              columns: [
                {
                  name: "col1",
                  external_type: "string",
                  type: "string",
                  sample_values: [],
                },
              ],
            },
          ],
        },
      ],
    },
  ],
};

const testDatasets = [
  {
    name: "dataset1",
    columns: [
      { name: "col1", type: "number" },
      { name: "col2", type: "string" },
    ],
  },
];
