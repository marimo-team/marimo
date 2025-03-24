/* Copyright 2024 Marimo. All rights reserved. */
import { expect, describe, it, afterAll, afterEach, beforeEach } from "vitest";
import { SQLCompletionStore, SQLLanguageAdapter } from "../sql";
import { store } from "@/core/state/jotai";
import {
  dataSourceConnectionsAtom,
  DEFAULT_ENGINE,
  type ConnectionName,
} from "@/core/datasets/data-source-connections";
import type { DataSourceConnection } from "@/core/kernel/messages";
import { PostgreSQL } from "@codemirror/lang-sql";

const adapter = new SQLLanguageAdapter();

describe("SQLLanguageAdapter", () => {
  describe("transformIn", () => {
    afterAll(() => {
      adapter.engine = DEFAULT_ENGINE;
      adapter.showOutput = true;
    });

    it("empty", () => {
      const [innerCode, offset] = adapter.transformIn("");
      expect(innerCode).toBe("");
      expect(offset).toBe(0);
      const out = adapter.transformOut(innerCode);
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
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM {df}");
      expect(adapter.dataframeName).toBe("_df");
      expect(offset).toBe(16);
    });

    it("should handle single double-quoted strings", () => {
      const pythonCode = 'next_df = mo.sql("SELECT * FROM {df}")';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM {df}");
      expect(adapter.dataframeName).toBe("next_df");
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
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM table");
      expect(adapter.showOutput).toBe(true);
      expect(offset).toBe(16);
    });

    it("should handle output flag set to False", () => {
      const pythonCode =
        '_df = mo.sql("""SELECT * FROM table""", output=False)';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM table");
      expect(adapter.showOutput).toBe(false);
      expect(offset).toBe(16);

      // handle trailing comma
      const pythonCode2 =
        '_df = mo.sql("""SELECT * FROM table""", output=False,)';
      const [innerCode2] = adapter.transformIn(pythonCode2);
      expect(innerCode2).toBe("SELECT * FROM table");
    });

    it("should default to showing output when flag is not specified", () => {
      const pythonCode = '_df = mo.sql("""SELECT * FROM table""")';
      adapter.transformIn(pythonCode);
      expect(adapter.showOutput).toBe(true);
    });

    it("should handle engine param when provided", () => {
      const pythonCode =
        '_df = mo.sql("""SELECT * FROM table""", engine=postgres_engine)';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM table");
      expect(offset).toBe(16);
      expect(adapter.engine).toBe("postgres_engine");

      // handle trailing comma
      const pythonCode2 =
        '_df = mo.sql("""SELECT * FROM table""", engine=postgres_engine,)';
      const [innerCode2] = adapter.transformIn(pythonCode2);
      expect(innerCode2).toBe("SELECT * FROM table");
    });

    it("should handle engine param with output flag", () => {
      const pythonCode =
        '_df = mo.sql("""SELECT * FROM table""", output=False, engine=postgres_engine)';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM table");
      expect(offset).toBe(16);
      expect(adapter.showOutput).toBe(false);
      expect(adapter.engine).toBe("postgres_engine");
    });

    it("should handle reversed order of params", () => {
      const pythonCode =
        '_df = mo.sql("""SELECT * FROM table""", engine=postgres_engine, output=False)';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM table");
      expect(offset).toBe(16);
      expect(adapter.showOutput).toBe(false);
      expect(adapter.engine).toBe("postgres_engine");
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
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe(
        `
SELECT name, price, category
FROM products
WHERE price < {price_threshold.value}
ORDER BY price DESC
        `.trim(),
      );
      expect(offset).toBe(22);
      expect(adapter.showOutput).toBe(true);
      expect(adapter.engine).toBe("sqlite");
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
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe(
        `
SELECT name, price, category
FROM products
WHERE price < {price_threshold.value}
ORDER BY price DESC
        `.trim(),
      );
      expect(offset).toBe(22);
    });

    it("should handle parametrized sql with inline double quotes f-string", () => {
      const pythonCode = `
_df = mo.sql(
    f"FROM products WHERE price < {price_threshold.value}",
    engine=sqlite,
)
`;
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe(
        "FROM products WHERE price < {price_threshold.value}",
      );
      expect(offset).toBe(20);
    });

    it("should handle parametrized sql with inline single quotes f-string", () => {
      const pythonCode = `
_df = mo.sql(
    f"FROM products WHERE price < {price_threshold.value}",
    engine=sqlite,
)
`;
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe(
        "FROM products WHERE price < {price_threshold.value}",
      );
      expect(offset).toBe(20);
    });
  });

  describe("transformOut", () => {
    afterEach(() => {
      adapter.engine = DEFAULT_ENGINE;
      adapter.showOutput = true;
      adapter.dataframeName = "_df";
    });

    it("should wrap SQL code with triple double-quoted string format", () => {
      const code = "SELECT * FROM {df}";
      adapter.lastQuotePrefix = "";
      adapter.dataframeName = "my_df";
      const [wrappedCode, offset] = adapter.transformOut(code);
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
      adapter.lastQuotePrefix = "f";
      adapter.dataframeName = "my_df";
      adapter.showOutput = false;
      const [wrappedCode, offset] = adapter.transformOut(code);
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
      adapter.lastQuotePrefix = "f";
      adapter.dataframeName = "my_df";
      adapter.showOutput = true;
      const [wrappedCode, offset] = adapter.transformOut(code);
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
      const pythonCode = '# hello\n_df = mo.sql("""SELECT * FROM {df}""")';
      const [innerCode] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM {df}");
      adapter.lastQuotePrefix = "f";
      adapter.dataframeName = "my_df";
      const [wrappedCode, offset] = adapter.transformOut(innerCode);
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
      adapter.engine = "postgres_engine" as ConnectionName;
      const [wrappedCode, offset] = adapter.transformOut(code);
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
      adapter.showOutput = false;
      adapter.engine = "postgres_engine" as ConnectionName;
      const [wrappedCode, offset] = adapter.transformOut(code);
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
        .set(DEFAULT_ENGINE, {
          name: DEFAULT_ENGINE,
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

    it("should use default engine initially", () => {
      expect(adapter.engine).toBe(DEFAULT_ENGINE);
    });

    it("should persist the selected engine", () => {
      const engine = "mysql_engine" as ConnectionName;
      adapter.selectEngine(engine);
      expect(adapter.engine).toBe(engine);
      expect(store.get(dataSourceConnectionsAtom).latestEngineSelected).toBe(
        engine,
      );

      adapter.selectEngine("postgres_engine" as ConnectionName);
      expect(adapter.engine).toBe("postgres_engine");
      expect(store.get(dataSourceConnectionsAtom).latestEngineSelected).toBe(
        "postgres_engine",
      );
    });

    it("should not change when engine is not in connectionsMap", () => {
      const engine = "unknown_engine" as ConnectionName;
      adapter.selectEngine(engine);
      expect(adapter.engine).toBe(engine);
      expect(
        store.get(dataSourceConnectionsAtom).latestEngineSelected,
      ).not.toBe("unknown_engine");
    });

    it("should update engine in transformIn when specified", () => {
      const pythonCode = '_df = mo.sql("""SELECT 1""", engine=postgres_engine)';
      adapter.transformIn(pythonCode);
      expect(adapter.engine).toBe("postgres_engine");
      expect(store.get(dataSourceConnectionsAtom).latestEngineSelected).toBe(
        "postgres_engine",
      );

      // Don't update for unspecified engine
      const pythonCode2 = '_df = mo.sql("""SELECT 1""")';
      adapter.transformIn(pythonCode2);
      expect(adapter.engine).toBe(DEFAULT_ENGINE);
      expect(store.get(dataSourceConnectionsAtom).latestEngineSelected).toBe(
        "postgres_engine",
      );

      // Don't update for unknown engine
      const pythonCode3 = '_df = mo.sql("""SELECT 1""", engine=unknown_engine)';
      adapter.transformIn(pythonCode3);
      expect(adapter.engine).toBe("unknown_engine");
      expect(store.get(dataSourceConnectionsAtom).latestEngineSelected).toBe(
        "postgres_engine",
      );
    });

    it("should maintain engine selection across transformIn/transformOut", () => {
      const engine = "postgres_engine" as ConnectionName;
      adapter.selectEngine(engine);

      const [innerCode] = adapter.transformIn(
        `_df = mo.sql("""SELECT 1""", engine=${engine})`,
      );
      expect(adapter.engine).toBe(engine);

      const [outCode] = adapter.transformOut(innerCode);
      expect(outCode).toContain(`engine=${engine}`);
    });

    it("should maintain engine when transforming empty string", () => {
      const engine = "postgres_engine" as ConnectionName;
      adapter.selectEngine(engine);

      const [innerCode] = adapter.transformIn("");
      expect(adapter.engine).toBe(engine);

      const [outCode] = adapter.transformOut(innerCode);
      expect(outCode).toContain(`engine=${engine}`);
    });

    it("should restore previous engine when selecting default", () => {
      const engine = "postgres_engine" as ConnectionName;
      adapter.selectEngine(engine);
      adapter.selectEngine(DEFAULT_ENGINE);

      expect(adapter.engine).toBe(DEFAULT_ENGINE);
      expect(store.get(dataSourceConnectionsAtom).latestEngineSelected).toBe(
        DEFAULT_ENGINE,
      );
    });
  });

  describe("getDefaultCode", () => {
    it("should include engine in getDefaultCode when selected", () => {
      const engine = "postgres_engine" as ConnectionName;
      adapter.selectEngine(engine);
      expect(adapter.getDefaultCode()).toBe(
        `_df = mo.sql(f"""SELECT * FROM """, engine=${engine})`,
      );
    });

    it("should not include engine in getDefaultCode when using default engine", () => {
      adapter.selectEngine(DEFAULT_ENGINE);
      expect(adapter.getDefaultCode()).toBe(
        `_df = mo.sql(f"""SELECT * FROM """)`,
      );
    });
  });
});

describe("tablesCompletionSource", () => {
  const mockStore = store;
  const completionStore = new SQLCompletionStore();

  beforeEach(() => {
    // Reset the adapter engine
    adapter.engine = DEFAULT_ENGINE;
  });

  it("should return null if connection not found", () => {
    mockStore.set(dataSourceConnectionsAtom, {
      connectionsMap: new Map(),
      latestEngineSelected: DEFAULT_ENGINE,
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

    adapter.engine = "test_engine" as ConnectionName;
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

    adapter.engine = "multi_db_engine" as ConnectionName;
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

    adapter.engine = "multi_db_engine" as ConnectionName;
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

    adapter.engine = "test_engine" as ConnectionName;
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

    adapter.engine = "test_engine" as ConnectionName;
    const completionSource = completionStore.getCompletionSource(
      "test_engine" as ConnectionName,
    );
    expect(completionSource?.defaultTable).toBe("users");
    expect(completionSource?.dialect).toBe(PostgreSQL);
  });
});
