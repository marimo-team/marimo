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
  aliasColumnCompletionSource,
  createCteCompletionSource,
  defaultSqlHoverTheme,
  NodeSqlParser,
  type NodeSqlParserResult,
  QueryContextAnalyzer,
  type SupportedDialects as ParserDialects,
  type SqlParseError,
  sqlExtension,
  SqlStructureAnalyzer,
  unqualifiedColumnCompletionSource,
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
const DEFAULT_PARSER_DIALECT: ParserDialects = "DuckDB";

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
export class SQLLanguageAdapter implements LanguageAdapter<SQLLanguageAdapterMetadata> {
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
    const analysis = createSQLAnalysis();
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
          // Completions based on the current query
          analysis.cteCompletionSource,
          analysis.aliasCompletionSource,
          analysis.columnCompletionSource,
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
          schema: getSchema,
          enableLinting: true,
          linterConfig: {
            delay: 250, // Delay before running validation
            parser: parser,
            // CustomSqlParser performs backend DuckDB validation in validateSql.
            perStatement: false,
          },
          enableSemanticLinting: true,
          semanticLinterConfig: {
            parser: analysis.parser,
            structureAnalyzer: analysis.structureAnalyzer,
            severity: {
              unknownTable: "off",
              unknownColumn: "warning",
              ambiguousColumn: "warning",
            },
          },
          enableGutterMarkers: true,
          gutterConfig: {
            backgroundColor: "#3b82f6", // Blue for current statement
            errorBackgroundColor: "#ef4444", // Red for invalid statements
            hideWhenNotFocused: true, // Hide gutter when editor loses focus
            parser: parser,
          },
          hoverConfig: {
            hoverTime: 300, // 300ms hover delay
            enableKeywords: true, // Show keyword information
            enableTables: true, // Show table information
            enableColumns: true, // Show column information
            parser: analysis.parser,
            contextAnalyzer: analysis.contextAnalyzer,
            theme: defaultSqlHoverTheme(theme),
          },
          enableNavigation: true,
          navigationConfig: {
            contextAnalyzer: analysis.contextAnalyzer,
            keymap: false,
            parser: analysis.parser,
            structureAnalyzer: analysis.structureAnalyzer,
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

function createSQLAnalysis() {
  const parser = new NodeSqlParser({
    getParserOptions: (state: EditorState) => {
      return {
        database: getAnalysisDialect(state),
      };
    },
  });
  const contextAnalyzer = new DialectAwareQueryContextAnalyzer(parser);
  const structureAnalyzer = new DialectAwareSqlStructureAnalyzer(parser);

  return {
    parser,
    contextAnalyzer,
    structureAnalyzer,
    cteCompletionSource: createCteCompletionSource({
      parser,
      contextAnalyzer,
      structureAnalyzer,
    }),
    aliasCompletionSource: aliasColumnCompletionSource({
      schema: getSchema,
      parser,
      contextAnalyzer,
    }),
    columnCompletionSource: unqualifiedColumnCompletionSource({
      schema: getSchema,
      parser,
      contextAnalyzer,
    }),
  };
}

function getAnalysisDialect(state: EditorState): ParserDialects {
  return guessParserDialect(state) ?? DEFAULT_PARSER_DIALECT;
}

class DialectAwareQueryContextAnalyzer extends QueryContextAnalyzer {
  private readonly analyzers = new Map<ParserDialects, QueryContextAnalyzer>();
  private readonly analysisParser: NodeSqlParser;

  constructor(analysisParser: NodeSqlParser) {
    super(analysisParser);
    this.analysisParser = analysisParser;
  }

  override getContext(
    sql: string,
    opts: { state: EditorState },
  ): ReturnType<QueryContextAnalyzer["getContext"]> {
    return this.getAnalyzer(opts.state).getContext(sql, opts);
  }

  override clearCache(): void {
    for (const analyzer of this.analyzers.values()) {
      analyzer.clearCache();
    }
  }

  private getAnalyzer(state: EditorState): QueryContextAnalyzer {
    const dialect = getAnalysisDialect(state);
    let analyzer = this.analyzers.get(dialect);
    if (!analyzer) {
      analyzer = new QueryContextAnalyzer(this.analysisParser);
      this.analyzers.set(dialect, analyzer);
    }
    return analyzer;
  }
}

class DialectAwareSqlStructureAnalyzer extends SqlStructureAnalyzer {
  private readonly analyzers = new Map<ParserDialects, SqlStructureAnalyzer>();
  private readonly analysisParser: NodeSqlParser;

  constructor(analysisParser: NodeSqlParser) {
    super(analysisParser);
    this.analysisParser = analysisParser;
  }

  override analyzeDocument(
    state: EditorState,
  ): ReturnType<SqlStructureAnalyzer["analyzeDocument"]> {
    return this.getAnalyzer(state).analyzeDocument(state);
  }

  override getStatementAtPosition(
    state: EditorState,
    position: number,
  ): ReturnType<SqlStructureAnalyzer["getStatementAtPosition"]> {
    return this.getAnalyzer(state).getStatementAtPosition(state, position);
  }

  override getStatementsInRange(
    state: EditorState,
    from: number,
    to: number,
  ): ReturnType<SqlStructureAnalyzer["getStatementsInRange"]> {
    return this.getAnalyzer(state).getStatementsInRange(state, from, to);
  }

  override clearCache(): void {
    for (const analyzer of this.analyzers.values()) {
      analyzer.clearCache();
    }
  }

  private getAnalyzer(state: EditorState): SqlStructureAnalyzer {
    const dialect = getAnalysisDialect(state);
    let analyzer = this.analyzers.get(dialect);
    if (!analyzer) {
      analyzer = new SqlStructureAnalyzer(this.analysisParser);
      this.analyzers.set(dialect, analyzer);
    }
    return analyzer;
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
    const dialect = connectionNameToParserDialect(metadata.engine);

    // Only validate if the editor is focused
    if (!this.isFocused) {
      return [];
    }

    // Only perform custom validation for DuckDB as we have a custom validation endpoint for it.
    if (!isDuckDBConnection(metadata.engine, dialect)) {
      return super.validateSql(sql, opts);
    }

    return this.validateWithDelay(
      sql,
      metadata.engine,
      dialect ?? DEFAULT_PARSER_DIALECT,
    );
  }

  override async parse(
    sql: string,
    opts: { state: EditorState },
  ): Promise<NodeSqlParserResult> {
    const metadata = getSQLMetadata(opts.state);
    const engine = metadata.engine;
    const dialect = connectionNameToParserDialect(engine);

    // For now, always return success for DuckDB
    if (isDuckDBConnection(engine, dialect)) {
      return { success: true, errors: [] };
    }

    return super.parse(sql, opts);
  }
}

function isDuckDBConnection(
  engine: ConnectionName,
  dialect: ParserDialects | null,
): boolean {
  return engine === DUCKDB_ENGINE || dialect === "DuckDB";
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

  const schema = config.schema;
  if (!isNamespaceMap(schema)) {
    return schema;
  }

  const defaultSchema = config.defaultSchema;
  const defaultSchemaNamespace = defaultSchema
    ? schema[defaultSchema]
    : undefined;

  // The completion schema contains both default-schema and fully qualified
  // paths. Promote default-schema tables so unqualified references resolve to
  // one exact match instead of appearing ambiguous.
  if (
    defaultSchemaNamespace &&
    !Array.isArray(defaultSchemaNamespace) &&
    typeof defaultSchemaNamespace === "object" &&
    "children" in defaultSchemaNamespace &&
    isNamespaceMap(defaultSchemaNamespace.children)
  ) {
    return {
      ...schema,
      ...Object.fromEntries(
        Object.entries(defaultSchemaNamespace.children).filter(
          ([name]) => !Object.hasOwn(schema, name),
        ),
      ),
    };
  }

  return schema;
}

function isNamespaceMap(
  namespace: SQLNamespace,
): namespace is Record<string, SQLNamespace> {
  if (Array.isArray(namespace)) {
    return false;
  }

  if (!("self" in namespace) || !("children" in namespace)) {
    return true;
  }

  // A self/children wrapper stores a Completion in `self`. A table or schema
  // literally named "self" stores another namespace there.
  const self = namespace.self;
  const isSelfChildrenWrapper =
    typeof self === "object" &&
    self !== null &&
    !Array.isArray(self) &&
    "label" in self &&
    typeof self.label === "string";

  return !isSelfChildrenWrapper;
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
    case "dremio":
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

export const exportedForTesting = {
  createSQLAnalysis,
  CustomSqlParser,
  getSchema,
};
