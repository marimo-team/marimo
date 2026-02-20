/* Copyright 2026 Marimo. All rights reserved. */

import { acceptCompletion, autocompletion } from "@codemirror/autocomplete";
import { insertTab } from "@codemirror/commands";
import { type SQLDialect, type SQLNamespace, sql } from "@codemirror/lang-sql";
import type { EditorState, Extension } from "@codemirror/state";
import { Compartment } from "@codemirror/state";
import {
  EditorView,
  keymap,
  ViewPlugin,
  type ViewUpdate,
} from "@codemirror/view";
import {
  defaultSqlHoverTheme,
  NodeSqlParser,
  type NodeSqlParserResult,
  type SupportedDialects as ParserDialects,
  type SqlParseError,
  sqlExtension,
} from "@marimo-team/codemirror-sql";
import { DuckDBDialect } from "@marimo-team/codemirror-sql/dialects";
import { type SQLMetadata, SQLParser } from "@marimo-team/smart-cells";
import type { CellId } from "@/core/cells/ids";
import { cellIdState } from "@/core/codemirror/cells/state";
import type { PlaceholderType } from "@/core/codemirror/config/types";
import type {
  CompletionConfig,
  DiagnosticsConfig,
  LSPConfig,
} from "@/core/config/config-schema";
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
import type { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import type { ValidateSQLResult } from "@/core/kernel/messages";
import { store } from "@/core/state/jotai";
import { resolvedThemeAtom } from "@/theme/useTheme";
import { logNever } from "@/utils/assertNever";
import { Logger } from "@/utils/Logger";
import { variableCompletionSource } from "../../embedded/embedded-python";
import { languageMetadataField } from "../../metadata";
import type { LanguageAdapter } from "../../types";
import {
  clearSqlValidationError,
  setSqlValidationError,
} from "./banner-validation-errors";
import {
  customKeywordCompletionSource,
  tablesCompletionSource,
} from "./completion-sources";
import { SCHEMA_CACHE } from "./completion-store";
import { getSQLMode, type SQLMode } from "./sql-mode";
import { isKnownDialect } from "./utils";

const DEFAULT_DIALECT = DuckDBDialect;
const DEFAULT_PARSER_DIALECT = "DuckDB";

// A compartment for the SQL config, so we can update the config of codemirror
const sqlConfigCompartment = new Compartment();

export interface SQLLanguageAdapterMetadata extends SQLMetadata {
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
  private parser = new SQLParser();
  readonly type = "sql";
  sqlModeEnabled: boolean;

  constructor() {
    this.sqlModeEnabled = true;
  }

  get defaultMetadata(): SQLLanguageAdapterMetadata {
    return {
      ...this.parser.defaultMetadata,
      engine: getLatestEngine() || DUCKDB_ENGINE,
    };
  }

  get defaultCode(): string {
    const engine = getLatestEngine();
    if (engine && engine !== DUCKDB_ENGINE) {
      return `_df = mo.sql(f"""SELECT * FROM """, engine=${engine})`;
    }
    return this.parser.defaultCode;
  }

  static fromQuery = (query: string) => SQLParser.fromQuery(query);

  transformIn(
    pythonCode: string,
  ): [
    sqlQuery: string,
    queryStartOffset: number,
    metadata: SQLLanguageAdapterMetadata,
  ] {
    this.parser.defaultMetadata.engine = getLatestEngine() || DUCKDB_ENGINE;
    const result = this.parser.transformIn(pythonCode);

    // Handle engine selection side effect
    const metadata = result.metadata as SQLLanguageAdapterMetadata;

    if (metadata.engine && metadata.engine !== DUCKDB_ENGINE) {
      setLatestEngineSelected(metadata.engine);
    }

    return [result.code, result.offset, metadata];
  }

  transformOut(
    code: string,
    metadata: SQLLanguageAdapterMetadata,
  ): [string, number] {
    const result = this.parser.transformOut(code, metadata);
    return [result.code, result.offset];
  }

  isSupported(pythonCode: string): boolean {
    return this.parser.isSupported(pythonCode);
  }

  getExtension(
    _cellId: CellId,
    _completionConfig: CompletionConfig,
    _hotkeys: HotkeyProvider,
    _placeholderType: PlaceholderType,
    lspConfig: LSPConfig & { diagnostics: DiagnosticsConfig },
  ): Extension[] {
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

    const sqlLinterEnabled = lspConfig?.diagnostics?.sql_linter ?? false;

    if (sqlLinterEnabled) {
      const theme = store.get(resolvedThemeAtom);
      const parser = new CustomSqlParser({
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
        EditorView.updateListener.of((update) => {
          if (update.focusChanged) {
            parser.setFocusState(update.view.hasFocus);
          }
        }),
      );
    }

    if (this.sqlModeEnabled) {
      extensions.push(sqlValidationExtension());
    }

    return extensions;
  }
}

class CustomSqlParser extends NodeSqlParser {
  private validationTimeout: number | null = null;
  private readonly VALIDATION_DELAY_MS = 300; // Wait 300ms after user stops typing
  private isFocused = false; // Only validate if the editor is focused

  setFocusState(focused: boolean) {
    this.isFocused = focused;
  }

  private async validateWithDelay(
    sql: string,
    engine: string,
    dialect: ParserDialects | null,
  ): Promise<SqlParseError[]> {
    // Clear any existing delay call
    if (this.validationTimeout) {
      window.clearTimeout(this.validationTimeout);
    }

    // Set up a new request to be called after the delay
    return new Promise((resolve) => {
      this.validationTimeout = window.setTimeout(async () => {
        // Only validate if the editor is still focused
        if (!this.isFocused) {
          resolve([]);
          return;
        }

        try {
          const sqlMode = getSQLMode();
          const result = await validateSQL(sql, engine, dialect, sqlMode);
          if (result.error) {
            Logger.error("Failed to validate SQL", { error: result.error });
            resolve([]);
            return;
          }
          resolve(result.parse_result?.errors ?? []);
        } catch (error) {
          Logger.error("Failed to validate SQL", { error });
          resolve([]);
        }
      }, this.VALIDATION_DELAY_MS);
    });
  }

  override async validateSql(
    sql: string,
    opts: { state: EditorState },
  ): Promise<SqlParseError[]> {
    const metadata = getSQLMetadata(opts.state);

    // Only validate if the editor is focused
    if (!this.isFocused) {
      return [];
    }

    // Only perform custom validation for DuckDB
    if (!INTERNAL_SQL_ENGINES.has(metadata.engine)) {
      return super.validateSql(sql, opts);
    }

    const dialect = guessParserDialect(opts.state);
    return this.validateWithDelay(sql, metadata.engine, dialect);
  }

  override async parse(
    sql: string,
    opts: { state: EditorState },
  ): Promise<NodeSqlParserResult> {
    const metadata = getSQLMetadata(opts.state);
    const engine = metadata.engine;

    // For now, always return success for DuckDB
    if (engine === DUCKDB_ENGINE) {
      return { success: true, errors: [] };
    }

    return super.parse(sql, opts);
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

  if (!dialect || !isKnownDialect(dialect)) {
    return null;
  }

  switch (dialect) {
    case "postgresql":
    case "postgres":
      return "PostgreSQL";
    case "db2":
    case "db2i":
      return "DB2";
    case "mysql":
      return "MySQL";
    case "sqlite":
      return "Sqlite";
    case "mssql":
    case "sqlserver":
    case "microsoft sql server":
      return "TransactSQL";
    case "duckdb":
      return "DuckDB";
    case "mariadb":
      return "MariaDB";
    case "cassandra":
      return "Noql";
    case "athena":
    case "awsathena":
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
    case "noql":
      return "Noql";
    case "oracle":
    case "oracledb":
    case "timescaledb":
    case "couchbase":
    case "trino":
    case "tidb":
    case "singlestoredb":
    case "spark":
    case "databricks":
    case "datafusion":
      Logger.debug("Unsupported dialect", { dialect });
      return null;
    default:
      logNever(dialect);
      return null;
  }
}

const SQL_VALIDATION_DEBOUNCE_MS = 300;

/**
 * Custom extension to run SQL queries in EXPLAIN mode on keypress.
 */
function sqlValidationExtension(): Extension {
  return ViewPlugin.define((view) => {
    let debounceTimeout: number | undefined;
    let lastValidationRequest: string | null = null;
    const cellId = view.state.facet(cellIdState);

    return {
      update(update: ViewUpdate) {
        // Only run validation if the document has changed
        // The extension only runs on keypress, so we don't need to check for focus
        // This lets AI completions / external calls trigger validation
        if (!update.docChanged) {
          return;
        }

        const sqlMode = getSQLMode();
        if (sqlMode === "default") {
          return;
        }

        const metadata = getSQLMetadata(update.state);
        const connectionName = metadata.engine;

        // Currently only DuckDB is supported
        if (!INTERNAL_SQL_ENGINES.has(connectionName)) {
          return;
        }

        const sqlContent = update.state.doc.toString();

        if (debounceTimeout) {
          window.clearTimeout(debounceTimeout);
        }

        debounceTimeout = window.setTimeout(async () => {
          // Skip if the SQL content has not changed
          if (lastValidationRequest === sqlContent) {
            return;
          }

          lastValidationRequest = sqlContent;

          if (sqlContent === "") {
            clearSqlValidationError(cellId);
            return;
          }

          try {
            const dialect = connectionNameToParserDialect(connectionName);
            const result = await validateSQL(
              sqlContent,
              connectionName,
              dialect,
              sqlMode,
            );
            const validateResult = result.validate_result;

            if (validateResult?.error_message) {
              setSqlValidationError({
                cellId,
                errorMessage: validateResult.error_message,
                dialect,
              });
            } else {
              clearSqlValidationError(cellId);
            }
          } catch (error) {
            Logger.error("Failed to validate SQL", { error });
          }
        }, SQL_VALIDATION_DEBOUNCE_MS);
      },

      // Remove side-effects on plugin removal
      destroy() {
        if (debounceTimeout) {
          window.clearTimeout(debounceTimeout);
        }
        clearSqlValidationError(cellId);
      },
    };
  });
}

/**
 * Determine if we should only parse or validate an SQL query.
 * The endpoint is cached, so we should use the same mode for all validation requests.
 */
async function validateSQL(
  sql: string,
  engine: string,
  dialect: ParserDialects | null,
  sqlMode: SQLMode,
): Promise<ValidateSQLResult> {
  const result = await ValidateSQL.request({
    onlyParse: sqlMode === "default",
    engine,
    dialect,
    query: sql,
  });

  if (result.error) {
    throw new Error(result.error);
  }
  return result;
}
