/* Copyright 2026 Marimo. All rights reserved. */

import { getIndentUnit } from "@codemirror/language";
import { StateEffect } from "@codemirror/state";
import type { EditorView } from "@codemirror/view";
import type { DialectOptions } from "sql-formatter";
import { logNever } from "@/utils/assertNever";
import { Logger } from "@/utils/Logger";
import { Objects } from "../../utils/objects";
import { getNotebook } from "../cells/cells";
import type { CellId } from "../cells/ids";
import { getResolvedMarimoConfig } from "../config/config";
import type { ConnectionName } from "../datasets/engines";
import { getRequestClient } from "../network/requests";
import { store } from "../state/jotai";
import { writeCellCode } from "./cell-documents";
import { notebookCellCodes } from "./copilot/getCodes";
import { languageAdapterState } from "./language/extension";
import { SCHEMA_CACHE } from "./language/languages/sql/completion-store";
import { isKnownDialect } from "./language/languages/sql/utils";
import { replaceEditorContent } from "./replace-editor-content";

export const formattingChangeEffect = StateEffect.define<boolean>();

/**
 * Format cells via the marimo server and write back the cells that changed.
 * Cells without an editor are formatted from the notebook document.
 */
export async function formatCells(cellIds: readonly CellId[]) {
  const allCodes = store.get(notebookCellCodes);
  const codes = Objects.fromEntries(
    cellIds
      .filter((cellId) => cellId in allCodes)
      .map((cellId) => [cellId, allCodes[cellId]]),
  );

  const { codes: formattedCodes } = await getRequestClient().sendFormat({
    codes,
    lineLength: getResolvedMarimoConfig().formatting.line_length,
  });

  const currentCodes = store.get(notebookCellCodes);
  for (const cellId of Objects.keys(codes)) {
    const formattedCode = formattedCodes[cellId];
    const unchanged =
      formattedCode === undefined || formattedCode === codes[cellId];
    const editedSinceRequest = currentCodes[cellId] !== codes[cellId];
    if (unchanged || editedSinceRequest) {
      continue;
    }
    writeCellCode(cellId, formattedCode, {
      effects: [formattingChangeEffect.of(true)],
    });
  }
}

/**
 * Format all cells in the notebook.
 */
export function formatAll() {
  return formatCells(getNotebook().cellIds);
}

/**
 * Format the SQL code in the editor view.
 *
 * This is currently only used by explicitly clicking the format button.
 * We do not use it for auto-formatting onSave or globally because
 * SQL formatting is much more opinionated than Python formatting, and we
 * don't want to tie the two together (just yet).
 */
export async function formatSQL(editor: EditorView, engine: ConnectionName) {
  // Lazy import sql-formatter
  const { formatDialect } = await import("sql-formatter");

  const sqlDialect = SCHEMA_CACHE.getInternalDialect(engine);
  const formatterDialect = await getSqlFormatterDialect(sqlDialect);

  // Get language adapter
  const languageAdapter = editor.state.field(languageAdapterState);
  const tabWidth = getIndentUnit(editor.state);
  if (languageAdapter.type !== "sql") {
    Logger.error("Language adapter is not SQL");
    return;
  }

  const codeAsSQL = editor.state.doc.toString();
  let formattedSQL: string;
  try {
    formattedSQL = formatDialect(codeAsSQL, {
      dialect: formatterDialect,
      tabWidth: tabWidth,
      useTabs: false,
    });
  } catch (error) {
    Logger.error("Error formatting SQL", { error });
    return;
  }

  // Update editor with formatted SQL
  replaceEditorContent(editor, formattedSQL, {
    effects: [formattingChangeEffect.of(true)],
  });
}

async function getSqlFormatterDialect(
  sqlDialect: string | null,
): Promise<DialectOptions> {
  const {
    bigquery,
    db2,
    db2i,
    duckdb,
    hive,
    mariadb,
    mysql,
    tidb,
    n1ql,
    plsql,
    postgresql,
    redshift,
    spark,
    sqlite,
    sql,
    trino,
    transactsql,
    singlestoredb,
    snowflake,
  } = await import("sql-formatter");

  const defaultDialect = sql;

  if (!sqlDialect || !isKnownDialect(sqlDialect)) {
    return defaultDialect;
  }
  switch (sqlDialect) {
    case "mysql":
      return mysql;
    case "mariadb":
      return mariadb;
    case "postgres":
    case "postgresql":
      return postgresql;
    case "sqlite":
      return sqlite;
    case "db2":
      return db2;
    case "db2i":
      return db2i;
    case "hive":
      return hive;
    case "redshift":
      return redshift;
    case "snowflake":
      return snowflake;
    case "trino":
      return trino;
    case "tidb":
      return tidb;
    case "oracle":
    case "oracledb":
      return plsql;
    case "spark":
      return spark;
    case "singlestoredb":
      return singlestoredb;
    case "couchbase":
      return n1ql;
    case "bigquery":
      return bigquery;
    case "duckdb":
      return duckdb;
    case "mssql":
    case "sqlserver":
    case "microsoft sql server":
      return transactsql;
    case "athena":
    case "awsathena":
    case "cassandra":
    case "noql":
    case "flink":
    case "mongodb":
    case "timescaledb":
    case "datafusion":
    case "dremio":
      return sql;
    case "databricks":
      return spark;
    default:
      logNever(sqlDialect);
      return defaultDialect;
  }
}
