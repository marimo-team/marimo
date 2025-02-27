/* Copyright 2024 Marimo. All rights reserved. */
import type { Extension } from "@codemirror/state";
import type { LanguageAdapter } from "./types";
import {
  sql,
  StandardSQL,
  schemaCompletionSource,
  MySQL,
  PostgreSQL,
  SQLite,
  type SQLDialect,
  type SQLConfig,
} from "@codemirror/lang-sql";
import dedent from "string-dedent";
import type { CompletionConfig } from "@/core/config/config-schema";
import type { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import { indentOneTab } from "./utils/indentOneTab";
import {
  autocompletion,
  type CompletionSource,
} from "@codemirror/autocomplete";
import { store } from "@/core/state/jotai";
import { type QuotePrefixKind, upgradePrefixKind } from "./utils/quotes";
import { capabilitiesAtom } from "@/core/config/capabilities";
import { MarkdownLanguageAdapter } from "./markdown";
import {
  dataConnectionsMapAtom,
  dataSourceConnectionsAtom,
  DEFAULT_ENGINE,
  setLatestEngineSelected,
  type ConnectionName,
} from "@/core/datasets/data-source-connections";
import { parser } from "@lezer/python";
import type { SyntaxNode, TreeCursor } from "@lezer/common";
import { parseArgsKwargs } from "./utils/ast";
import { Logger } from "@/utils/Logger";
import { LRUCache } from "@/utils/lru";
import type { DataSourceConnection } from "@/core/kernel/messages";

/**
 * Language adapter for SQL.
 */
export class SQLLanguageAdapter implements LanguageAdapter {
  readonly type = "sql";
  readonly defaultCode = `_df = mo.sql(f"""SELECT * FROM """)`;
  static fromQuery = (query: string) => `_df = mo.sql(f"""${query.trim()}""")`;

  dataframeName = "_df";
  lastQuotePrefix: QuotePrefixKind = "f";
  showOutput = true;
  engine = store.get(dataSourceConnectionsAtom).latestEngineSelected;

  getDefaultCode(): string {
    if (this.engine === DEFAULT_ENGINE) {
      return this.defaultCode;
    }
    return `_df = mo.sql(f"""SELECT * FROM """, engine=${this.engine})`;
  }

  transformIn(
    pythonCode: string,
  ): [sqlQuery: string, queryStartOffset: number] {
    if (!this.isSupported(pythonCode)) {
      // Attempt to remove any markdown wrappers
      const [transformedCode, offset] =
        new MarkdownLanguageAdapter().transformIn(pythonCode);
      // Just return the original code
      return [transformedCode, offset];
    }

    pythonCode = pythonCode.trim();

    // Handle empty strings
    if (pythonCode === "") {
      this.lastQuotePrefix = "f";
      this.showOutput = true;
      return ["", 0];
    }

    const sqlStatement = parseSQLStatement(pythonCode);
    if (sqlStatement) {
      this.dataframeName = sqlStatement.dfName;
      this.showOutput = sqlStatement.output ?? true;
      this.engine = (sqlStatement.engine as ConnectionName) ?? DEFAULT_ENGINE;

      if (this.engine !== DEFAULT_ENGINE) {
        // User selected a new engine, set it as latest.
        // This makes new SQL statements use the new engine by default.
        setLatestEngineSelected(this.engine);
      }

      return [
        dedent(`\n${sqlStatement.sqlString}\n`).trim(),
        sqlStatement.startPosition,
      ];
    }

    return [pythonCode, 0];
  }

  transformOut(code: string): [string, number] {
    // Get the quote type from the last transformIn
    const prefix = upgradePrefixKind(this.lastQuotePrefix, code);

    // Multiline code
    const start = `${this.dataframeName} = mo.sql(\n    ${prefix}"""\n`;
    const escapedCode = code.replaceAll('"""', String.raw`\"""`);

    const showOutputParam = this.showOutput ? "" : ",\n    output=False";
    const engineParam =
      this.engine === DEFAULT_ENGINE ? "" : `,\n    engine=${this.engine}`;
    const end = `\n    """${showOutputParam}${engineParam}\n)`;

    return [start + indentOneTab(escapedCode) + end, start.length + 1];
  }

  isSupported(pythonCode: string): boolean {
    const sqlCapabilities = store.get(capabilitiesAtom).sql;
    if (!sqlCapabilities) {
      return false;
    }

    if (pythonCode.trim() === "") {
      return true;
    }

    // Does not have 2 `mo.sql` calls
    if (pythonCode.split("mo.sql").length > 2) {
      return false;
    }

    // Has at least one `mo.sql` call
    if (!pythonCode.includes("mo.sql")) {
      return false;
    }

    return parseSQLStatement(pythonCode) !== null;
  }

  selectEngine(connectionName: ConnectionName): void {
    this.engine = connectionName;
    setLatestEngineSelected(this.engine);
  }

  setShowOutput(showOutput: boolean): void {
    this.showOutput = showOutput;
  }

  setDataframeName(dataframeName: string): void {
    this.dataframeName = dataframeName;
  }

  getExtension(
    _completionConfig: CompletionConfig,
    _hotkeys: HotkeyProvider,
  ): Extension[] {
    return [
      sql({
        dialect: StandardSQL,
      }),
      autocompletion({
        activateOnTyping: true,
      }),
      StandardSQL.language.data.of({
        autocomplete: tablesCompletionSource(this),
      }),
    ];
  }
}

export class SQLCompletionStore {
  private cache = new LRUCache<DataSourceConnection, SQLConfig>(10);

  getCompletionSource(connectionName: ConnectionName): SQLConfig | null {
    const dataConnectionsMap = store.get(dataConnectionsMapAtom);
    const connection = dataConnectionsMap.get(connectionName);
    if (!connection) {
      return null;
    }

    let cacheConfig: SQLConfig | undefined = this.cache.get(connection);
    if (!cacheConfig) {
      type TableMap = Record<string, string[]>;
      type SchemaMap = Record<string, TableMap>;
      type DatabaseMap = Record<string, SchemaMap>;

      const mapping: DatabaseMap | SchemaMap = {};

      // When there is default db and schema, we can use the table name directly
      // Otherwise, we need to use the fully qualified name
      for (const database of connection.databases) {
        // If there is only one database, it is the default
        const isDefaultDb =
          connection.default_database === database.name ||
          connection.databases.length === 1;

        for (const schema of database.schemas) {
          for (const table of schema.tables) {
            const columns = table.columns.map((col) => col.name);

            if (isDefaultDb) {
              const schemaMap = mapping[schema.name] ?? {};
              schemaMap[table.name] = columns;
              mapping[schema.name] = schemaMap;
            } else {
              const dbMap = (mapping[database.name] ?? {}) as Record<
                string,
                Record<string, string[]>
              >;
              const schemaMap = dbMap[schema.name] ?? {};
              schemaMap[table.name] = columns;
              dbMap[schema.name] = schemaMap;
              mapping[database.name] = dbMap;
            }
          }
        }
      }

      cacheConfig = {
        dialect: guessDialect(connection),
        schema: mapping,
        defaultSchema: connection.default_schema ?? undefined,
        defaultTable: getSingleTable(connection),
      };
      this.cache.set(connection, cacheConfig);
    }

    return cacheConfig;
  }
}

const SCHEMA_CACHE = new SQLCompletionStore();

function tablesCompletionSource(adapter: SQLLanguageAdapter): CompletionSource {
  return (ctx) => {
    const connectionName = adapter.engine;
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

function findAssignment(cursor: TreeCursor): SyntaxNode | null {
  do {
    if (cursor.name === "AssignStatement") {
      return cursor.node;
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
export function parseSQLStatement(code: string): SQLParseInfo | null {
  try {
    const tree = parser.parse(code);
    const cursor = tree.cursor();

    // Find assignment statement
    const assignStmt = findAssignment(cursor);
    if (!assignStmt) {
      return null;
    }

    // Code outside of the assignment statement is not allowed
    const outsideCode =
      code.slice(0, assignStmt.from) + code.slice(assignStmt.to);
    if (outsideCode.trim().length > 0) {
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
