/* Copyright 2024 Marimo. All rights reserved. */

import {
  autocompletion,
  type CompletionSource,
} from "@codemirror/autocomplete";
import {
  keywordCompletionSource,
  MSSQL,
  MySQL,
  PostgreSQL,
  type SQLConfig,
  type SQLDialect,
  SQLite,
  StandardSQL,
  schemaCompletionSource,
  sql,
} from "@codemirror/lang-sql";
import type { Extension } from "@codemirror/state";
import type { SyntaxNode, TreeCursor } from "@lezer/common";
import { parser } from "@lezer/python";
// @ts-expect-error: no declaration file
import dedent from "string-dedent";
import { isSchemaless } from "@/components/datasources/utils";
import {
  type ConnectionName,
  DUCKDB_ENGINE,
  dataConnectionsMapAtom,
  dataSourceConnectionsAtom,
  setLatestEngineSelected,
} from "@/core/datasets/data-source-connections";
import { datasetTablesAtom } from "@/core/datasets/state";
import type { DataSourceConnection } from "@/core/kernel/messages";
import { store } from "@/core/state/jotai";
import { Logger } from "@/utils/Logger";
import { LRUCache } from "@/utils/lru";
import { variableCompletionSource } from "../embedded/embedded-python";
import { languageMetadataField } from "../metadata";
import type { LanguageAdapter } from "../types";
import { parseArgsKwargs } from "../utils/ast";
import { indentOneTab } from "../utils/indentOneTab";
import type { QuotePrefixKind } from "../utils/quotes";
import { MarkdownLanguageAdapter } from "./markdown";

export interface SQLLanguageAdapterMetadata {
  dataframeName: string;
  quotePrefix: QuotePrefixKind;
  commentLines: string[];
  showOutput: boolean;
  engine: ConnectionName;
}

function getLatestEngine(): ConnectionName {
  return store.get(dataSourceConnectionsAtom).latestEngineSelected;
}

/**
 * Language adapter for SQL.
 */
export class SQLLanguageAdapter
  implements LanguageAdapter<SQLLanguageAdapterMetadata>
{
  readonly type = "sql";
  get defaultMetadata(): SQLLanguageAdapterMetadata {
    return {
      dataframeName: "_df",
      quotePrefix: "f",
      commentLines: [],
      showOutput: true,
      engine: getLatestEngine() || this.defaultEngine,
    };
  }

  get defaultCode(): string {
    const latestEngine = getLatestEngine();
    if (latestEngine === this.defaultEngine) {
      return `_df = mo.sql(f"""SELECT * FROM """)`;
    }
    return `_df = mo.sql(f"""SELECT * FROM """, engine=${latestEngine})`;
  }

  static fromQuery = (query: string) => `_df = mo.sql(f"""${query.trim()}""")`;

  private readonly defaultEngine = DUCKDB_ENGINE;

  transformIn(
    pythonCode: string,
  ): [
    sqlQuery: string,
    queryStartOffset: number,
    metadata: SQLLanguageAdapterMetadata,
  ] {
    pythonCode = pythonCode.trim();

    // Default metadata
    const metadata: SQLLanguageAdapterMetadata = {
      ...this.defaultMetadata,
      commentLines: this.extractCommentLines(pythonCode),
    };

    if (!this.isSupported(pythonCode)) {
      // Attempt to remove any markdown wrappers
      const [transformedCode, offset] =
        new MarkdownLanguageAdapter().transformIn(pythonCode);
      // Just return the original code
      return [transformedCode, offset, metadata];
    }

    // Handle empty strings
    if (pythonCode === "") {
      return ["", 0, metadata];
    }

    const sqlStatement = parseSQLStatement(pythonCode);
    if (sqlStatement) {
      metadata.dataframeName = sqlStatement.dfName;
      metadata.showOutput = sqlStatement.output ?? true;
      metadata.engine =
        (sqlStatement.engine as ConnectionName) ?? this.defaultEngine;

      if (metadata.engine !== this.defaultEngine) {
        // User selected a new engine, set it as latest.
        // This makes new SQL statements use the new engine by default.
        setLatestEngineSelected(metadata.engine);
      }

      return [
        dedent(`\n${sqlStatement.sqlString}\n`).trim(),
        sqlStatement.startPosition,
        metadata,
      ];
    }

    return [pythonCode, 0, metadata];
  }

  transformOut(
    code: string,
    metadata: SQLLanguageAdapterMetadata,
  ): [string, number] {
    const { quotePrefix, commentLines, showOutput, engine, dataframeName } =
      metadata;

    const start = `${dataframeName} = mo.sql(\n    ${quotePrefix}"""\n`;
    const escapedCode = code.replaceAll('"""', String.raw`\"""`);

    const showOutputParam = showOutput ? "" : ",\n    output=False";
    const engineParam =
      engine === this.defaultEngine ? "" : `,\n    engine=${engine}`;
    const end = `\n    """${showOutputParam}${engineParam}\n)`;

    return [
      [...commentLines, start].join("\n") + indentOneTab(escapedCode) + end,
      start.length + 1,
    ];
  }

  isSupported(pythonCode: string): boolean {
    if (pythonCode.trim() === "") {
      return true;
    }

    // Has at least one `mo.sql` call
    if (!pythonCode.includes("mo.sql")) {
      return false;
    }

    // Does not have 2 `mo.sql` calls
    if (pythonCode.split("mo.sql").length > 2) {
      return false;
    }

    return parseSQLStatement(pythonCode) !== null;
  }

  private extractCommentLines(pythonCode: string): string[] {
    const lines = pythonCode.split("\n");
    const commentLines = [];
    for (const line of lines) {
      if (line.startsWith("#")) {
        commentLines.push(line);
      } else {
        break;
      }
    }
    return commentLines;
  }

  getExtension(): Extension[] {
    const keywordCompletion = keywordCompletionSource(StandardSQL);
    return [
      sql({
        dialect: StandardSQL,
      }),
      autocompletion({
        // We remove the default keymap because we use our own which
        // handles the Escape key correctly in Vim
        defaultKeymap: false,
        activateOnTyping: true,
        override: [
          tablesCompletionSource(),
          // Complete for variables in SQL {} blocks
          variableCompletionSource,
          (ctx) => {
            // We want to ignore keyword completions on something like
            // `WHERE my_table.col`
            //                    ^cursor
            const textBefore = ctx.matchBefore(/\.\w*/);
            if (textBefore) {
              // If there is a match, we are typing after a dot,
              // so we don't want to trigger SQL keyword completion
              return null;
            }

            const result = keywordCompletion(ctx);
            return result;
          },
        ],
      }),
    ];
  }
}

type TableToCols = Record<string, string[]>;
type Schemas = Record<string, TableToCols>;

export class SQLCompletionStore {
  private cache = new LRUCache<[DataSourceConnection, TableToCols], SQLConfig>(
    10,
  );

  getCompletionSource(connectionName: ConnectionName): SQLConfig | null {
    const dataConnectionsMap = store.get(dataConnectionsMapAtom);
    const connection = dataConnectionsMap.get(connectionName);
    if (!connection) {
      return null;
    }

    const localTables = store.get(datasetTablesAtom);

    // If there is a conflict with connection tables,
    // the engine will prioritize the connection tables without special handling
    const tablesMap: TableToCols = {};
    for (const table of localTables) {
      const tableColumns = table.columns.map((col) => col.name);
      tablesMap[table.name] = tableColumns;
    }

    const cacheKey: [DataSourceConnection, TableToCols] = [
      connection,
      tablesMap,
    ];

    let cacheConfig: SQLConfig | undefined = this.cache.get(cacheKey);
    if (!cacheConfig) {
      const schemaMap: Record<string, TableToCols> = {};
      const databaseMap: Record<string, Schemas> = {};

      const baseConfig: SQLConfig = {
        dialect: guessDialect(connection),
        schema: schemaMap,
        defaultSchema: connection.default_schema ?? undefined,
        defaultTable: getSingleTable(connection),
      };

      // When there is only one database, it is the default
      const defaultDb = connection.databases.find(
        (db) =>
          db.name === connection.default_database ||
          connection.databases.length === 1,
      );

      const dbToVerify = defaultDb ?? connection.databases[0];
      const isSchemalessDb =
        dbToVerify?.schemas.some((schema) => isSchemaless(schema.name)) ??
        false;

      // For schemaless databases, treat databases as schemas
      if (isSchemalessDb) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const dbToTablesMap: Record<string, any> = {};

        for (const db of connection.databases) {
          const isDefaultDb = db.name === defaultDb?.name;

          for (const schema of db.schemas) {
            for (const table of schema.tables) {
              const columns = table.columns.map((col) => col.name);

              if (isDefaultDb) {
                // For default database, add tables directly to top level
                dbToTablesMap[table.name] = columns;
              } else {
                // Otherwise nest under database name
                dbToTablesMap[db.name] = dbToTablesMap[db.name] || {};
                dbToTablesMap[db.name][table.name] = columns;
              }
            }
          }
        }

        cacheConfig = {
          ...baseConfig,
          schema: dbToTablesMap,
          defaultSchema: defaultDb?.name,
        };
        return cacheConfig;
      }

      // For default db, we can use the schema name directly
      for (const schema of defaultDb?.schemas ?? []) {
        schemaMap[schema.name] = {};
        for (const table of schema.tables) {
          const columns = table.columns.map((col) => col.name);
          schemaMap[schema.name][table.name] = columns;
        }
      }

      // Otherwise, we need to use the fully qualified name
      for (const database of connection.databases) {
        if (database.name === defaultDb?.name) {
          continue;
        }
        databaseMap[database.name] = {};

        for (const schema of database.schemas) {
          databaseMap[database.name][schema.name] = {};

          for (const table of schema.tables) {
            const columns = table.columns.map((col) => col.name);
            databaseMap[database.name][schema.name][table.name] = columns;
          }
        }
      }

      cacheConfig = {
        ...baseConfig,
        schema: { ...databaseMap, ...schemaMap, ...tablesMap },
        defaultSchema: connection.default_schema ?? undefined,
      };
      this.cache.set(cacheKey, cacheConfig);
    }

    return cacheConfig;
  }
}

const SCHEMA_CACHE = new SQLCompletionStore();

function tablesCompletionSource(): CompletionSource {
  return (ctx) => {
    const metadata = ctx.state.field(
      languageMetadataField,
    ) as SQLLanguageAdapterMetadata;
    const connectionName = metadata.engine;
    const config = SCHEMA_CACHE.getCompletionSource(connectionName);

    if (!config) {
      return null;
    }

    return schemaCompletionSource(config)(ctx);
  };
}

function getSingleTable(connection: DataSourceConnection): string | undefined {
  if (connection.databases.length !== 1) {
    return undefined;
  }
  const database = connection.databases[0];
  if (database.schemas.length !== 1) {
    return undefined;
  }
  const schema = database.schemas[0];
  if (schema.tables.length !== 1) {
    return undefined;
  }
  return schema.tables[0].name;
}

function guessDialect(
  connection: DataSourceConnection,
): SQLDialect | undefined {
  switch (connection.dialect) {
    case "postgresql":
    case "postgres":
      return PostgreSQL;
    case "mysql":
      return MySQL;
    case "sqlite":
      return SQLite;
    case "mssql":
    case "sqlserver":
      return MSSQL;
    default:
      return undefined;
  }
}

interface SQLParseInfo {
  dfName: string;
  sqlString: string;
  engine: string | undefined;
  output: boolean | undefined;
  startPosition: number;
}

// Finds an assignment node that is preceded only by comments.
function findAssignment(cursor: TreeCursor): SyntaxNode | null {
  do {
    if (cursor.name === "AssignStatement") {
      return cursor.node;
    }

    if (cursor.name !== "Comment") {
      return null;
    }
  } while (cursor.next());
  return null;
}

function getStringContent(node: SyntaxNode, code: string): string | null {
  // Handle triple quoted strings
  if (node.name === "String") {
    const content = code.slice(node.from, node.to);
    // Remove quotes and trim
    if (content.startsWith('"""') || content.startsWith("'''")) {
      return safeDedent(content.slice(3, -3));
    }
    // Handle single quoted strings
    return safeDedent(content.slice(1, -1));
  }
  // Handle f-strings
  if (node.name === "FormatString") {
    const content = code.slice(node.from, node.to);
    if (content.startsWith('f"""') || content.startsWith("f'''")) {
      return safeDedent(content.slice(4, -3));
    }
    return safeDedent(content.slice(2, -1));
  }
  return null;
}

/**
 * Parses a SQL statement from a Python code string.
 *
 * @param code - The Python code string to parse.
 * @returns The parsed SQL statement or null if parsing fails.
 */
function parseSQLStatement(code: string): SQLParseInfo | null {
  try {
    const tree = parser.parse(code);
    const cursor = tree.cursor();

    // Trees start with a Script node.
    if (cursor.name === "Script") {
      cursor.next();
    }
    const assignStmt = findAssignment(cursor);
    if (!assignStmt) {
      return null;
    }

    // Code after the assignment statement is not allowed.
    if (code.slice(assignStmt.to).trim().length > 0) {
      return null;
    }

    let dfName: string | null = null;
    let sqlString: string | null = null;
    let engine: string | undefined;
    let output: boolean | undefined;
    let startPosition = 0;

    // Parse the assignment
    const assignCursor = assignStmt.cursor();
    assignCursor.firstChild(); // Move to first child of assignment

    // First child should be the variable name
    if (assignCursor.name === "VariableName") {
      dfName = code.slice(assignCursor.from, assignCursor.to);
    }

    if (!dfName) {
      return null;
    }

    // Move to the expression part (after the =)
    while (assignCursor.next()) {
      if (assignCursor.name === "CallExpression") {
        // Check if it's mo.sql call
        const callCursor = assignCursor.node.cursor();
        let isMoSql = false;

        callCursor.firstChild(); // Move to first child of call
        if (callCursor.name === "MemberExpression") {
          const memberText = code.slice(callCursor.from, callCursor.to);
          isMoSql = memberText === "mo.sql";
        }

        if (!isMoSql) {
          return null;
        }

        // Move to arguments
        while (callCursor.next()) {
          if (callCursor.name === "ArgList") {
            const argListCursor = callCursor.node.cursor();

            const { args, kwargs } = parseArgsKwargs(argListCursor, code);

            // Parse positional args (SQL query)
            if (args.length === 1) {
              sqlString = getStringContent(args[0], code);
              startPosition =
                args[0].from +
                getPrefixLength(code.slice(args[0].from, args[0].to));
            }

            // Parse kwargs (engine and output)
            for (const { key, value } of kwargs) {
              switch (key) {
                case "engine":
                  engine = value;
                  break;
                case "output":
                  output = value === "True";
                  break;
              }
            }

            // Check if sql string is empty
            if (sqlString === "") {
              return { dfName, sqlString: "", engine, output, startPosition };
            }

            break;
          }
        }
      }
    }

    if (!dfName || !sqlString) {
      return null;
    }

    return {
      dfName,
      sqlString,
      engine,
      output,
      startPosition,
    };
  } catch (error) {
    Logger.warn("Failed to parse SQL statement", { error: error });
    return null;
  }
}

function getPrefixLength(code: string): number {
  if (code === "") {
    return 0;
  }
  if (code.startsWith('f"""') || code.startsWith("f'''")) {
    return 4;
  }
  if (code.startsWith('"""') || code.startsWith("'''")) {
    return 3;
  }
  if (code.startsWith("f'") || code.startsWith('f"')) {
    return 2;
  }
  if (code.startsWith("'") || code.startsWith('"')) {
    return 1;
  }
  return 0;
}

function safeDedent(code: string): string {
  try {
    // Dedent expects the first and last line to be empty / contain only whitespace, so we pad with \n
    return dedent(`\n${code}\n`).trim();
  } catch {
    return code;
  }
}
