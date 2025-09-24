/* Copyright 2024 Marimo. All rights reserved. */

import { acceptCompletion, autocompletion } from "@codemirror/autocomplete";
import { insertTab } from "@codemirror/commands";
import { type SQLDialect, type SQLNamespace, sql } from "@codemirror/lang-sql";
import type { EditorState, Extension } from "@codemirror/state";
import { Compartment } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";
import type { SyntaxNode, TreeCursor } from "@lezer/common";
import { parser } from "@lezer/python";
import {
  defaultSqlHoverTheme,
  NodeSqlParser,
  type SupportedDialects as ParserDialects,
  sqlExtension,
} from "@marimo-team/codemirror-sql";
import { DuckDBDialect } from "@marimo-team/codemirror-sql/dialects";
import dedent from "string-dedent";
import { cellIdState } from "@/core/codemirror/cells/state";
import { getFeatureFlag } from "@/core/config/feature-flag";
import {
  dataSourceConnectionsAtom,
  setLatestEngineSelected,
} from "@/core/datasets/data-source-connections";
import {
  type ConnectionName,
  DUCKDB_ENGINE,
  INTERNAL_SQL_ENGINES,
} from "@/core/datasets/engines";
import { ValidateSQL } from "@/core/datasets/request-registry";
import type { ValidateSQLResult } from "@/core/kernel/messages";
import { store } from "@/core/state/jotai";
import { resolvedThemeAtom } from "@/theme/useTheme";
import { Logger } from "@/utils/Logger";
import { variableCompletionSource } from "../../embedded/embedded-python";
import { languageMetadataField } from "../../metadata";
import type { LanguageAdapter } from "../../types";
import { parseArgsKwargs } from "../../utils/ast";
import { indentOneTab } from "../../utils/indentOneTab";
import type { QuotePrefixKind } from "../../utils/quotes";
import { MarkdownLanguageAdapter } from "../markdown";
import {
  customKeywordCompletionSource,
  tablesCompletionSource,
} from "./completion-sources";
import { SCHEMA_CACHE } from "./completion-store";
import { getSQLMode } from "./sql-mode";
import {
  clearSqlValidationError,
  setSqlValidationError,
} from "./validation-errors";

const DEFAULT_DIALECT = DuckDBDialect;
const DEFAULT_PARSER_DIALECT = "DuckDB";

// A compartment for the SQL config, so we can update the config of codemirror
const sqlConfigCompartment = new Compartment();

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
  sqlLinterEnabled: boolean;
  sqlModeEnabled: boolean;

  constructor() {
    try {
      this.sqlLinterEnabled = getFeatureFlag("sql_linter");
      this.sqlModeEnabled = getFeatureFlag("sql_mode");
    } catch {
      this.sqlLinterEnabled = false;
      this.sqlModeEnabled = false;
    }
  }

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
    const extensions = [
      // This can be updated with a dispatch effect
      sqlConfigCompartment.of(sql({ dialect: DEFAULT_DIALECT })),
      keymap.of([
        {
          key: "Tab",
          // When tab is pressed, we want to accept the completion or insert a tab
          run: (cm) => {
            return acceptCompletion(cm) || insertTab(cm);
          },
          preventDefault: true,
        },
      ]),
      autocompletion({
        // We remove the default keymap because we use our own which
        // handles the Escape key correctly in Vim
        defaultKeymap: false,
        activateOnTyping: true,
        override: [
          // Completions for schema
          tablesCompletionSource(),
          // Complete for variables in SQL {} blocks
          variableCompletionSource,
          // Completions for dialect keywords
          customKeywordCompletionSource(),
        ],
      }),
    ];

    if (this.sqlLinterEnabled) {
      const theme = store.get(resolvedThemeAtom);
      const parser = new NodeSqlParser({
        getParserOptions: (state: EditorState) => {
          return {
            database: guessParserDialect(state) ?? DEFAULT_PARSER_DIALECT,
          };
        },
      });

      extensions.push(
        sqlExtension({
          enableLinting: true,
          linterConfig: {
            delay: 250, // Delay before running validation
            parser: parser,
          },
          enableGutterMarkers: true,
          gutterConfig: {
            backgroundColor: "#3b82f6", // Blue for current statement
            errorBackgroundColor: "#ef4444", // Red for invalid statements
            hideWhenNotFocused: true, // Hide gutter when editor loses focus
            parser: parser,
          },
          hoverConfig: {
            schema: getSchema, // Use the same schema as autocomplete
            hoverTime: 300, // 300ms hover delay
            enableKeywords: true, // Show keyword information
            enableTables: true, // Show table information
            enableColumns: true, // Show column information
            parser: parser,
            theme: defaultSqlHoverTheme(theme),
          },
        }),
      );
    }

    if (this.sqlModeEnabled) {
      extensions.push(sqlValidationExtension());
    }

    return extensions;
  }
}

/**
 * Update the SQL dialect in the editor view.
 */
function updateSQLDialect(view: EditorView, dialect: SQLDialect) {
  view.dispatch({
    effects: sqlConfigCompartment.reconfigure(sql({ dialect })),
  });
}

// Helper functions to update the SQL dialect

export function updateSQLDialectFromConnection(
  view: EditorView,
  connectionName: ConnectionName,
) {
  const dialect = SCHEMA_CACHE.getDialect(connectionName);
  updateSQLDialect(view, dialect);
}

export function initializeSQLDialect(view: EditorView) {
  // Get current engine and update dialect
  const metadata = getSQLMetadata(view.state);
  const connectionName = metadata.engine;
  const dialect = SCHEMA_CACHE.getDialect(connectionName);

  updateSQLDialect(view, dialect);
}

function getSQLMetadata(state: EditorState): SQLLanguageAdapterMetadata {
  return state.field(languageMetadataField) as SQLLanguageAdapterMetadata;
}

function getSchema(view: EditorView): SQLNamespace {
  const metadata = getSQLMetadata(view.state);
  const connectionName = metadata.engine;
  const config = SCHEMA_CACHE.getCompletionSource(connectionName);
  if (!config?.schema) {
    return {};
  }

  return config.schema;
}

function guessParserDialect(state: EditorState): ParserDialects | null {
  const metadata = getSQLMetadata(state);
  const connectionName = metadata.engine;
  return connectionNameToParserDialect(connectionName);
}

function connectionNameToParserDialect(
  connectionName: ConnectionName,
): ParserDialects | null {
  const dialect =
    SCHEMA_CACHE.getInternalDialect(connectionName)?.toLowerCase();
  switch (dialect) {
    case "postgresql":
    case "postgres":
      return "PostgreSQL";
    case "db2":
      return "DB2";
    case "mysql":
      return "MySQL";
    case "sqlite":
      return "Sqlite";
    case "mssql":
    case "sqlserver":
      return "TransactSQL";
    case "duckdb":
      return "DuckDB";
    case "mariadb":
      return "MariaDB";
    case "cassandra":
      return "Noql";
    case "athena":
      return "Athena";
    case "bigquery":
      return "BigQuery";
    case "hive":
      return "Hive";
    case "redshift":
      return "Redshift";
    case "snowflake":
      return "Snowflake";
    case "flink":
      return "FlinkSQL";
    case "mongodb":
      return "Noql";
    default:
      return null;
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

function sqlValidationExtension(): Extension {
  let debounceTimeout: NodeJS.Timeout | null = null;
  let lastValidationRequest: string | null = null;

  return EditorView.updateListener.of((update) => {
    const sqlMode = getSQLMode();
    if (sqlMode !== "validate") {
      return;
    }

    const metadata = getSQLMetadata(update.state);
    const connectionName = metadata.engine;
    if (!INTERNAL_SQL_ENGINES.has(connectionName)) {
      // Currently only internal engines are supported
      return;
    }

    if (!update.docChanged) {
      return;
    }

    const doc = update.state.doc;
    const sqlContent = doc.toString();

    // Clear existing timeout
    if (debounceTimeout) {
      clearTimeout(debounceTimeout);
    }

    // Debounce the validation call
    debounceTimeout = setTimeout(async () => {
      // Skip if content hasn't changed since last validation
      if (lastValidationRequest === sqlContent) {
        return;
      }

      lastValidationRequest = sqlContent;
      const cellId = update.view.state.facet(cellIdState);

      if (sqlContent === "") {
        clearSqlValidationError(cellId);
        return;
      }

      try {
        const result: ValidateSQLResult = await ValidateSQL.request({
          engine: connectionName,
          query: sqlContent,
        });

        if (result.error) {
          const dialect = connectionNameToParserDialect(connectionName);
          setSqlValidationError({ cellId, error: result.error, dialect });
        } else {
          clearSqlValidationError(cellId);
        }
      } catch (error) {
        Logger.warn("Failed to validate SQL", { error });
      }
    }, 300);
  });
}
