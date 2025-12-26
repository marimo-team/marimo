/* Copyright 2026 Marimo. All rights reserved. */

import type {
  CompletionContext,
  CompletionResult,
} from "@codemirror/autocomplete";
import { PostgreSQL } from "@codemirror/lang-sql";
import { EditorState, type Extension } from "@codemirror/state";
import { DuckDBDialect } from "@marimo-team/codemirror-sql/dialects";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { CellId } from "@/core/cells/ids";
import type {
  CompletionConfig,
  DiagnosticsConfig,
  LSPConfig,
} from "@/core/config/config-schema";
import type { DataSourceConnection } from "@/core/datasets/data-source-connections";
import {
  dataSourceConnectionsAtom,
  setLatestEngineSelected,
} from "@/core/datasets/data-source-connections";
import { type ConnectionName, DUCKDB_ENGINE } from "@/core/datasets/engines";
import { datasetsAtom } from "@/core/datasets/state";
import type { DatasetsState } from "@/core/datasets/types";
import type { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import { store } from "@/core/state/jotai";
import type { PlaceholderType } from "../../config/types";
import { TestSQLCompletionStore } from "../languages/sql/completion-store";
import {
  SQLLanguageAdapter,
  type SQLLanguageAdapterMetadata,
} from "../languages/sql/sql";
import { languageMetadataField } from "../metadata";

const adapter = new SQLLanguageAdapter();

const TEST_ENGINE = "test_engine" as ConnectionName;

const TEST_EXTENSION_ARGS = [
  {} as CellId,
  {} as CompletionConfig,
  {} as HotkeyProvider,
  {} as PlaceholderType,
  {} as LSPConfig & {
    diagnostics: DiagnosticsConfig;
  },
] as const;

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
  const completionStore = new TestSQLCompletionStore();

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

    const completionSource = completionStore.getCompletionSource(TEST_ENGINE);
    expect(completionSource).toBe(null);
  });

  it("should create schema with schema.table structure", () => {
    const mockConnection: DataSourceConnection = {
      name: TEST_ENGINE,
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
                  num_columns: 0,
                  num_rows: 0,
                  variable_name: null,
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
                  num_columns: 0,
                  num_rows: 0,
                  variable_name: null,
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
      connectionsMap: new Map([[TEST_ENGINE, mockConnection]]),
      latestEngineSelected: TEST_ENGINE,
    });

    const completionSource = completionStore.getCompletionSource(TEST_ENGINE);
    expect(completionSource?.defaultTable).toBeUndefined();
    expect(completionSource?.dialect).toBe(DuckDBDialect);
    expect(completionSource?.schema).toMatchInlineSnapshot(`
      {
        "public": {
          "children": {
            "orders": {
              "children": [
                {
                  "info": [Function],
                  "label": "order_id",
                  "type": "column",
                },
                {
                  "info": [Function],
                  "label": "user_id",
                  "type": "column",
                },
                {
                  "info": [Function],
                  "label": "total",
                  "type": "column",
                },
              ],
              "self": {
                "info": [Function],
                "label": "orders",
                "type": "table",
              },
            },
            "users": {
              "children": [
                {
                  "info": [Function],
                  "label": "id",
                  "type": "column",
                },
                {
                  "info": [Function],
                  "label": "name",
                  "type": "column",
                },
                {
                  "info": [Function],
                  "label": "email",
                  "type": "column",
                },
              ],
              "self": {
                "info": [Function],
                "label": "users",
                "type": "table",
              },
            },
          },
          "self": {
            "detail": "public",
            "info": [Function],
            "label": "public",
            "type": "schema",
          },
        },
        "test_db": {
          "children": {
            "public": {
              "children": {
                "orders": {
                  "children": [
                    {
                      "info": [Function],
                      "label": "order_id",
                      "type": "column",
                    },
                    {
                      "info": [Function],
                      "label": "user_id",
                      "type": "column",
                    },
                    {
                      "info": [Function],
                      "label": "total",
                      "type": "column",
                    },
                  ],
                  "self": {
                    "info": [Function],
                    "label": "orders",
                    "type": "table",
                  },
                },
                "users": {
                  "children": [
                    {
                      "info": [Function],
                      "label": "id",
                      "type": "column",
                    },
                    {
                      "info": [Function],
                      "label": "name",
                      "type": "column",
                    },
                    {
                      "info": [Function],
                      "label": "email",
                      "type": "column",
                    },
                  ],
                  "self": {
                    "info": [Function],
                    "label": "users",
                    "type": "table",
                  },
                },
              },
              "self": {
                "detail": "test_db.public",
                "info": [Function],
                "label": "public",
                "type": "schema",
              },
            },
          },
          "self": {
            "detail": "test_db",
            "info": [Function],
            "label": "test_db",
            "type": "database",
          },
        },
      }
    `);
  });

  it("should handle multiple databases and schemas", () => {
    const mockConnection: DataSourceConnection = {
      name: "multi_db_engine" as ConnectionName,
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
                  num_columns: 0,
                  num_rows: 0,
                  variable_name: null,
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
                  num_columns: 0,
                  num_rows: 0,
                  variable_name: null,
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
      connectionsMap: new Map([[mockConnection.name, mockConnection]]),
      latestEngineSelected: mockConnection.name,
    });

    const completionSource = completionStore.getCompletionSource(
      "multi_db_engine" as ConnectionName,
    );
    // expect fully qualified 'database.schema.table' names
    // as there is no default database
    expect(completionSource?.schema).toMatchInlineSnapshot(`
      {
        "db1": {
          "children": {
            "schema1": {
              "children": {
                "table1": {
                  "children": [
                    {
                      "info": [Function],
                      "label": "col1",
                      "type": "column",
                    },
                  ],
                  "self": {
                    "info": [Function],
                    "label": "table1",
                    "type": "table",
                  },
                },
              },
              "self": {
                "detail": "db1.schema1",
                "info": [Function],
                "label": "schema1",
                "type": "schema",
              },
            },
          },
          "self": {
            "detail": "db1",
            "info": [Function],
            "label": "db1",
            "type": "database",
          },
        },
        "db2": {
          "children": {
            "schema2": {
              "children": {
                "table2": {
                  "children": [
                    {
                      "info": [Function],
                      "label": "col2",
                      "type": "column",
                    },
                  ],
                  "self": {
                    "info": [Function],
                    "label": "table2",
                    "type": "table",
                  },
                },
              },
              "self": {
                "detail": "db2.schema2",
                "info": [Function],
                "label": "schema2",
                "type": "schema",
              },
            },
          },
          "self": {
            "detail": "db2",
            "info": [Function],
            "label": "db2",
            "type": "database",
          },
        },
      }
    `);
    expect(completionSource?.defaultTable).toBeUndefined();
  });

  it("should handle multiple databases and schemas with default", () => {
    const mockConnection: DataSourceConnection = {
      name: "multi_db_engine" as ConnectionName,
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
                  num_columns: 0,
                  num_rows: 0,
                  variable_name: null,
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
                  num_columns: 0,
                  num_rows: 0,
                  variable_name: null,
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
                  num_columns: 0,
                  num_rows: 0,
                  variable_name: null,
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
                  num_columns: 0,
                  num_rows: 0,
                  variable_name: null,
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
      connectionsMap: new Map([[mockConnection.name, mockConnection]]),
      latestEngineSelected: mockConnection.name,
    });

    const completionSource = completionStore.getCompletionSource(
      "multi_db_engine" as ConnectionName,
    );
    expect(completionSource?.schema).toMatchInlineSnapshot(`
      {
        "db1": {
          "children": {
            "schema1": {
              "children": {
                "table1": {
                  "children": [
                    {
                      "info": [Function],
                      "label": "col1",
                      "type": "column",
                    },
                  ],
                  "self": {
                    "info": [Function],
                    "label": "table1",
                    "type": "table",
                  },
                },
              },
              "self": {
                "detail": "db1.schema1",
                "info": [Function],
                "label": "schema1",
                "type": "schema",
              },
            },
            "schema2": {
              "children": {
                "table2": {
                  "children": [
                    {
                      "info": [Function],
                      "label": "col2",
                      "type": "column",
                    },
                  ],
                  "self": {
                    "info": [Function],
                    "label": "table2",
                    "type": "table",
                  },
                },
              },
              "self": {
                "detail": "db1.schema2",
                "info": [Function],
                "label": "schema2",
                "type": "schema",
              },
            },
          },
          "self": {
            "detail": "db1",
            "info": [Function],
            "label": "db1",
            "type": "database",
          },
        },
        "db2": {
          "children": {
            "schema2": {
              "children": {
                "table2": {
                  "children": [
                    {
                      "info": [Function],
                      "label": "col2",
                      "type": "column",
                    },
                  ],
                  "self": {
                    "info": [Function],
                    "label": "table2",
                    "type": "table",
                  },
                },
              },
              "self": {
                "detail": "db2.schema2",
                "info": [Function],
                "label": "schema2",
                "type": "schema",
              },
            },
          },
          "self": {
            "detail": "db2",
            "info": [Function],
            "label": "db2",
            "type": "database",
          },
        },
        "db3": {
          "children": {
            "schema2": {
              "children": {
                "table2": {
                  "children": [
                    {
                      "info": [Function],
                      "label": "col2",
                      "type": "column",
                    },
                  ],
                  "self": {
                    "info": [Function],
                    "label": "table2",
                    "type": "table",
                  },
                },
              },
              "self": {
                "detail": "db3.schema2",
                "info": [Function],
                "label": "schema2",
                "type": "schema",
              },
            },
          },
          "self": {
            "detail": "db3",
            "info": [Function],
            "label": "db3",
            "type": "database",
          },
        },
        "schema1": {
          "children": {
            "table1": {
              "children": [
                {
                  "info": [Function],
                  "label": "col1",
                  "type": "column",
                },
              ],
              "self": {
                "info": [Function],
                "label": "table1",
                "type": "table",
              },
            },
          },
          "self": {
            "detail": "schema1",
            "info": [Function],
            "label": "schema1",
            "type": "schema",
          },
        },
        "schema2": {
          "children": {
            "table2": {
              "children": [
                {
                  "info": [Function],
                  "label": "col2",
                  "type": "column",
                },
              ],
              "self": {
                "info": [Function],
                "label": "table2",
                "type": "table",
              },
            },
          },
          "self": {
            "detail": "schema2",
            "info": [Function],
            "label": "schema2",
            "type": "schema",
          },
        },
      }
    `);
    expect(completionSource?.defaultTable).toBeUndefined();
    expect(completionSource?.defaultSchema).toBe("schema2");
  });

  it("should handle default schema", () => {
    const mockConnection: DataSourceConnection = {
      name: TEST_ENGINE,
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
                  num_columns: 0,
                  num_rows: 0,
                  variable_name: null,
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
      connectionsMap: new Map([[mockConnection.name, mockConnection]]),
      latestEngineSelected: mockConnection.name,
    });

    const completionSource = completionStore.getCompletionSource(TEST_ENGINE);
    expect(completionSource?.schema).toMatchInlineSnapshot(`
      {
        "public": {
          "children": {
            "users": {
              "children": [
                {
                  "info": [Function],
                  "label": "id",
                  "type": "column",
                },
                {
                  "info": [Function],
                  "label": "name",
                  "type": "column",
                },
                {
                  "info": [Function],
                  "label": "email",
                  "type": "column",
                },
              ],
              "self": {
                "info": [Function],
                "label": "users",
                "type": "table",
              },
            },
          },
          "self": {
            "detail": "public",
            "info": [Function],
            "label": "public",
            "type": "schema",
          },
        },
        "test_db": {
          "children": {
            "public": {
              "children": {
                "users": {
                  "children": [
                    {
                      "info": [Function],
                      "label": "id",
                      "type": "column",
                    },
                    {
                      "info": [Function],
                      "label": "name",
                      "type": "column",
                    },
                    {
                      "info": [Function],
                      "label": "email",
                      "type": "column",
                    },
                  ],
                  "self": {
                    "info": [Function],
                    "label": "users",
                    "type": "table",
                  },
                },
              },
              "self": {
                "detail": "test_db.public",
                "info": [Function],
                "label": "public",
                "type": "schema",
              },
            },
          },
          "self": {
            "detail": "test_db",
            "info": [Function],
            "label": "test_db",
            "type": "database",
          },
        },
      }
    `);
    expect(completionSource?.defaultTable).toBe("users");
    expect(completionSource?.defaultSchema).toBe("public");
  });

  it("should create a default table if there is only one table", () => {
    const mockConnection: DataSourceConnection = {
      name: TEST_ENGINE,
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
                  num_columns: 0,
                  num_rows: 0,
                  variable_name: null,
                  columns: [],
                },
              ],
            },
          ],
        },
      ],
    };

    mockStore.set(dataSourceConnectionsAtom, {
      connectionsMap: new Map([[mockConnection.name, mockConnection]]),
      latestEngineSelected: mockConnection.name,
    });

    const completionSource = completionStore.getCompletionSource(TEST_ENGINE);
    expect(completionSource?.defaultTable).toBe("users");
    expect(completionSource?.dialect).toBe(PostgreSQL);
  });

  it("should handle schemaless databases", () => {
    const mockConnection: DataSourceConnection = {
      name: TEST_ENGINE,
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
                  num_columns: 0,
                  num_rows: 0,
                  variable_name: null,
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
                  num_columns: 0,
                  num_rows: 0,
                  variable_name: null,
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
      connectionsMap: new Map([[mockConnection.name, mockConnection]]),
      latestEngineSelected: mockConnection.name,
    });

    const completionSource = completionStore.getCompletionSource(TEST_ENGINE);
    expect(completionSource?.defaultTable).toBe(undefined);
    expect(completionSource?.dialect).toBe(PostgreSQL);
    expect(completionSource?.schema).toMatchInlineSnapshot(`
      {
        "test_db": {
          "children": {},
          "self": {
            "detail": "test_db",
            "info": [Function],
            "label": "test_db",
            "type": "database",
          },
        },
        "test_db2": {
          "children": {
            "orders": {
              "children": [
                {
                  "info": [Function],
                  "label": "order_id",
                  "type": "column",
                },
              ],
              "self": {
                "info": [Function],
                "label": "orders",
                "type": "table",
              },
            },
          },
          "self": {
            "detail": "test_db2",
            "info": [Function],
            "label": "test_db2",
            "type": "database",
          },
        },
        "users": {
          "children": [
            {
              "info": [Function],
              "label": "id",
              "type": "column",
            },
          ],
          "self": {
            "info": [Function],
            "label": "users",
            "type": "table",
          },
        },
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

    describe("SQL Completions", () => {
      const completionStore = new TestSQLCompletionStore();

      beforeEach(() => {
        // Reset state
        setLatestEngineSelected(DUCKDB_ENGINE);
        store.set(datasetsAtom, {
          tables: [],
        } as unknown as DatasetsState);
        store.set(dataSourceConnectionsAtom, {
          connectionsMap: new Map(),
          latestEngineSelected: DUCKDB_ENGINE,
        });
      });

      const createEditorState = (
        doc: string,
        metadata?: Partial<SQLLanguageAdapterMetadata>,
      ) => {
        const defaultMetadata: SQLLanguageAdapterMetadata = {
          dataframeName: "_df",
          quotePrefix: "f",
          commentLines: [],
          showOutput: true,
          engine: DUCKDB_ENGINE,
          ...metadata,
        };

        return EditorState.create({
          doc,
          extensions: [languageMetadataField.init(() => defaultMetadata)],
        });
      };

      const createCompletionContext = (
        state: EditorState,
        pos: number,
        matchText?: string,
        matchFrom?: number,
      ): CompletionContext => {
        return {
          pos,
          explicit: false,
          matchBefore: matchText
            ? () => ({
                from: matchFrom || pos - matchText.length,
                to: pos,
                text: matchText,
              })
            : () => null,
          state,
          aborted: false,
          tokenBefore: () => null,
        } as unknown as CompletionContext;
      };

      const getCompletion = (extensions: Extension[]) => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const ext = extensions.find((ext) => (ext as any).facet === undefined);
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        return (ext as any)?.value?.override?.[0];
      };

      describe("tablesCompletionSource", () => {
        it("should return null when no connection exists", () => {
          const state = createEditorState("SELECT * FROM ");
          const ctx = createCompletionContext(state, 14);

          const adapter = new SQLLanguageAdapter();
          const extensions = adapter.getExtension(...TEST_EXTENSION_ARGS);
          const completion = getCompletion(extensions);

          expect(completion).toBeDefined();
          const result = completion!(ctx);
          expect(result).toBeNull();
        });

        it("should provide table completions when connection exists", () => {
          const mockConnection: DataSourceConnection = {
            name: TEST_ENGINE,
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
                        num_columns: 0,
                        num_rows: 0,
                        variable_name: null,
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
                        ],
                      },
                    ],
                  },
                ],
              },
            ],
          };

          store.set(dataSourceConnectionsAtom, {
            connectionsMap: new Map([[TEST_ENGINE, mockConnection]]),
            latestEngineSelected: TEST_ENGINE,
          });

          const state = createEditorState("SELECT * FROM u", {
            engine: TEST_ENGINE,
          });
          const ctx = createCompletionContext(state, 15, "u", 14);

          const adapter = new SQLLanguageAdapter();
          const extensions = adapter.getExtension(...TEST_EXTENSION_ARGS);
          const completion = getCompletion(extensions);

          expect(completion).toBeDefined();
          const result = completion!(ctx);
          expect(result).toBeDefined();
          expect(result?.options.length).toBeGreaterThan(0);
        });

        it("should include local datasets in completions", () => {
          const mockConnection: DataSourceConnection = {
            name: TEST_ENGINE,
            dialect: "duckdb",
            display_name: "duckdb",
            source: "duckdb",
            databases: [],
          };

          store.set(dataSourceConnectionsAtom, {
            connectionsMap: new Map([[TEST_ENGINE, mockConnection]]),
            latestEngineSelected: TEST_ENGINE,
          });

          store.set(datasetsAtom, { tables: testDatasets } as DatasetsState);

          const state = createEditorState("SELECT * FROM d", {
            engine: TEST_ENGINE,
          });
          const ctx = createCompletionContext(state, 15, "d", 14);

          const adapter = new SQLLanguageAdapter();
          const extensions = adapter.getExtension(...TEST_EXTENSION_ARGS);
          const completion = getCompletion(extensions);

          expect(completion).toBeDefined();
          const result: CompletionResult = completion!(ctx);
          expect(result).toBeDefined();
          expect(result?.options.some((opt) => opt.label === "dataset1")).toBe(
            true,
          );
        });
      });

      describe("customKeywordCompletionSource", () => {
        it("should provide SQL keyword completions", () => {
          const mockConnection: DataSourceConnection = {
            name: TEST_ENGINE,
            dialect: "postgres",
            display_name: "postgres",
            source: "postgres",
            databases: [],
          };

          store.set(dataSourceConnectionsAtom, {
            connectionsMap: new Map([[TEST_ENGINE, mockConnection]]),
            latestEngineSelected: TEST_ENGINE,
          });

          const state = createEditorState("SEL", {
            engine: TEST_ENGINE,
          });
          const ctx = createCompletionContext(state, 3, "SEL", 0);

          const adapter = new SQLLanguageAdapter();
          const extensions = adapter.getExtension(...TEST_EXTENSION_ARGS);
          const completion = getCompletion(extensions);

          expect(completion).toBeDefined();
          const result: CompletionResult = completion!(ctx);
          expect(result).toBeDefined();
          expect(result?.options.some((opt) => opt.label === "SELECT")).toBe(
            true,
          );
        });

        it("should not provide keyword completions after dot", () => {
          const mockConnection: DataSourceConnection = {
            name: TEST_ENGINE,
            dialect: "postgres",
            display_name: "postgres",
            source: "postgres",
            databases: [],
          };

          store.set(dataSourceConnectionsAtom, {
            connectionsMap: new Map([[TEST_ENGINE, mockConnection]]),
            latestEngineSelected: TEST_ENGINE,
          });

          const state = createEditorState("SELECT users.n", {
            engine: TEST_ENGINE,
          });
          const ctx = createCompletionContext(state, 14, ".n", 12);

          const adapter = new SQLLanguageAdapter();
          const extensions = adapter.getExtension(...TEST_EXTENSION_ARGS);
          const completion = getCompletion(extensions);

          expect(completion).toBeDefined();
          const result = completion!(ctx);
          expect(result).toBeNull();
        });

        it("should use correct dialect for different engines", () => {
          const mysqlConnection: DataSourceConnection = {
            name: "mysql_engine" as ConnectionName,
            dialect: "mysql",
            display_name: "mysql",
            source: "mysql",
            databases: [],
          };

          store.set(dataSourceConnectionsAtom, {
            connectionsMap: new Map([[mysqlConnection.name, mysqlConnection]]),
            latestEngineSelected: mysqlConnection.name,
          });

          // Test that the correct dialect is used
          const dialect = completionStore.getDialect(mysqlConnection.name);
          expect(dialect).toBeDefined();
          expect(dialect?.spec.keywords).toBeDefined();
        });
      });

      describe("variableCompletionSource", () => {
        it("should be included in extension overrides", () => {
          const adapter = new SQLLanguageAdapter();
          const extensions = adapter.getExtension(...TEST_EXTENSION_ARGS);
          const completion = getCompletion(extensions);

          expect(completion).toBeDefined();
          expect(completion).toHaveLength(3); // tablesCompletionSource, variableCompletionSource, customKeywordCompletionSource
        });
      });
    });
    mockStore.set(datasetsAtom, { tables: testDatasets } as DatasetsState);

    const mockConnection: DataSourceConnection = {
      name: TEST_ENGINE,
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
                  num_columns: 0,
                  num_rows: 0,
                  variable_name: null,
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
      connectionsMap: new Map([[TEST_ENGINE, mockConnection]]),
      latestEngineSelected: TEST_ENGINE,
    });

    const completionSource = completionStore.getCompletionSource(TEST_ENGINE);
    expect(completionSource?.schema).toMatchInlineSnapshot(`
      {
        "dataset1": {
          "children": [
            {
              "info": [Function],
              "label": "col1",
              "type": "column",
            },
            {
              "info": [Function],
              "label": "col2",
              "type": "column",
            },
          ],
          "self": {
            "info": [Function],
            "label": "dataset1",
            "type": "table",
          },
        },
        "test_db": {
          "children": {
            "test_schema": {
              "children": {
                "dataset2": {
                  "children": [
                    {
                      "info": [Function],
                      "label": "col1",
                      "type": "column",
                    },
                  ],
                  "self": {
                    "info": [Function],
                    "label": "dataset2",
                    "type": "table",
                  },
                },
              },
              "self": {
                "detail": "test_db.test_schema",
                "info": [Function],
                "label": "test_schema",
                "type": "schema",
              },
            },
          },
          "self": {
            "detail": "test_db",
            "info": [Function],
            "label": "test_db",
            "type": "database",
          },
        },
        "test_schema": {
          "children": {
            "dataset2": {
              "children": [
                {
                  "info": [Function],
                  "label": "col1",
                  "type": "column",
                },
              ],
              "self": {
                "info": [Function],
                "label": "dataset2",
                "type": "table",
              },
            },
          },
          "self": {
            "detail": "test_schema",
            "info": [Function],
            "label": "test_schema",
            "type": "schema",
          },
        },
      }
    `);
  });

  it("should return new connection tables when connection is updated", () => {
    mockStore.set(dataSourceConnectionsAtom, {
      connectionsMap: new Map([[TEST_ENGINE, mockConnection]]),
      latestEngineSelected: TEST_ENGINE,
    });

    const completionSource = completionStore.getCompletionSource(TEST_ENGINE);
    expect(completionSource?.schema).toMatchInlineSnapshot(`
      {
        "test_db": {
          "children": {
            "test_schema": {
              "children": {
                "dataset2": {
                  "children": [
                    {
                      "info": [Function],
                      "label": "col1",
                      "type": "column",
                    },
                  ],
                  "self": {
                    "info": [Function],
                    "label": "dataset2",
                    "type": "table",
                  },
                },
              },
              "self": {
                "detail": "test_db.test_schema",
                "info": [Function],
                "label": "test_schema",
                "type": "schema",
              },
            },
          },
          "self": {
            "detail": "test_db",
            "info": [Function],
            "label": "test_db",
            "type": "database",
          },
        },
        "test_schema": {
          "children": {
            "dataset2": {
              "children": [
                {
                  "info": [Function],
                  "label": "col1",
                  "type": "column",
                },
              ],
              "self": {
                "info": [Function],
                "label": "dataset2",
                "type": "table",
              },
            },
          },
          "self": {
            "detail": "test_schema",
            "info": [Function],
            "label": "test_schema",
            "type": "schema",
          },
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
        [TEST_ENGINE, newConnection],
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ]) as any,
      latestEngineSelected: TEST_ENGINE,
    });

    const completionSource2 = completionStore.getCompletionSource(TEST_ENGINE);
    expect(completionSource2?.defaultSchema).toBe("new_schema");
  });

  it("should return new local tables when local tables are updated", () => {
    mockStore.set(dataSourceConnectionsAtom, {
      connectionsMap: new Map([
        [TEST_ENGINE, mockConnection],
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ]) as any,
      latestEngineSelected: TEST_ENGINE,
    });
    mockStore.set(datasetsAtom, { tables: testDatasets } as DatasetsState);
    const completionSource = completionStore.getCompletionSource(TEST_ENGINE);
    expect(completionSource?.schema).toMatchInlineSnapshot(`
      {
        "dataset1": {
          "children": [
            {
              "info": [Function],
              "label": "col1",
              "type": "column",
            },
            {
              "info": [Function],
              "label": "col2",
              "type": "column",
            },
          ],
          "self": {
            "info": [Function],
            "label": "dataset1",
            "type": "table",
          },
        },
        "test_db": {
          "children": {
            "test_schema": {
              "children": {
                "dataset2": {
                  "children": [
                    {
                      "info": [Function],
                      "label": "col1",
                      "type": "column",
                    },
                  ],
                  "self": {
                    "info": [Function],
                    "label": "dataset2",
                    "type": "table",
                  },
                },
              },
              "self": {
                "detail": "test_db.test_schema",
                "info": [Function],
                "label": "test_schema",
                "type": "schema",
              },
            },
          },
          "self": {
            "detail": "test_db",
            "info": [Function],
            "label": "test_db",
            "type": "database",
          },
        },
        "test_schema": {
          "children": {
            "dataset2": {
              "children": [
                {
                  "info": [Function],
                  "label": "col1",
                  "type": "column",
                },
              ],
              "self": {
                "info": [Function],
                "label": "dataset2",
                "type": "table",
              },
            },
          },
          "self": {
            "detail": "test_schema",
            "info": [Function],
            "label": "test_schema",
            "type": "schema",
          },
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

    const newCompletionSource =
      completionStore.getCompletionSource(TEST_ENGINE);
    expect(newCompletionSource?.schema).toMatchInlineSnapshot(`
      {
        "dataset3": {
          "children": [
            {
              "info": [Function],
              "label": "col1",
              "type": "column",
            },
            {
              "info": [Function],
              "label": "col2",
              "type": "column",
            },
          ],
          "self": {
            "info": [Function],
            "label": "dataset3",
            "type": "table",
          },
        },
        "test_db": {
          "children": {
            "test_schema": {
              "children": {
                "dataset2": {
                  "children": [
                    {
                      "info": [Function],
                      "label": "col1",
                      "type": "column",
                    },
                  ],
                  "self": {
                    "info": [Function],
                    "label": "dataset2",
                    "type": "table",
                  },
                },
              },
              "self": {
                "detail": "test_db.test_schema",
                "info": [Function],
                "label": "test_schema",
                "type": "schema",
              },
            },
          },
          "self": {
            "detail": "test_db",
            "info": [Function],
            "label": "test_db",
            "type": "database",
          },
        },
        "test_schema": {
          "children": {
            "dataset2": {
              "children": [
                {
                  "info": [Function],
                  "label": "col1",
                  "type": "column",
                },
              ],
              "self": {
                "info": [Function],
                "label": "dataset2",
                "type": "table",
              },
            },
          },
          "self": {
            "detail": "test_schema",
            "info": [Function],
            "label": "test_schema",
            "type": "schema",
          },
        },
      }
    `);
  });
});

const mockConnection: DataSourceConnection = {
  name: TEST_ENGINE,
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
              num_columns: 0,
              num_rows: 0,
              variable_name: null,
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
