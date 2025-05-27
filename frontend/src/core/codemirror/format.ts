/* Copyright 2024 Marimo. All rights reserved. */

import type { EditorView } from "@codemirror/view";
import type { CellId } from "../cells/ids";
import { Objects } from "../../utils/objects";
import { sendFormat } from "../network/requests";
import { getNotebook } from "../cells/cells";
import { notebookCellEditorViews } from "../cells/utils";
import {
  getEditorCodeAsPython,
  updateEditorCodeFromPython,
} from "./language/utils";
import { StateEffect } from "@codemirror/state";
import { getResolvedMarimoConfig } from "../config/config";
import { cellActionsState } from "./cells/state";
import { languageAdapterState } from "./language/extension";
import { Logger } from "@/utils/Logger";
import { cellIdState } from "./config/extension";
import { getIndentUnit } from "@codemirror/language";

export const formattingChangeEffect = StateEffect.define<boolean>();

/**
 * Format the code in the editor views via the marimo server,
 * and update the editor views with the formatted code.
 */
export async function formatEditorViews(views: Record<CellId, EditorView>) {
  const codes = Objects.mapValues(views, (view) => getEditorCodeAsPython(view));

  const formatResponse = await sendFormat({
    codes,
    lineLength: getResolvedMarimoConfig().formatting.line_length,
  });

  for (const [cellIdString, formattedCode] of Objects.entries(
    formatResponse.codes,
  )) {
    const cellId = cellIdString as CellId;
    const originalCode = codes[cellId];
    const view = views[cellId];

    if (!view) {
      continue;
    }

    // Only update the editor view if the formatted code is different
    // from the original code
    if (formattedCode === originalCode) {
      continue;
    }

    const actions = view.state.facet(cellActionsState);
    actions.updateCellCode({
      cellId,
      code: formattedCode,
      formattingChange: true,
    });
    updateEditorCodeFromPython(view, formattedCode);
  }
}

/**
 * Format all cells in the notebook.
 */
export function formatAll() {
  const views = notebookCellEditorViews(getNotebook());
  return formatEditorViews(views);
}

/**
 * Format the SQL code in the editor view.
 *
 * This is currently only used by explicitly clicking the format button.
 * We do not use it for auto-formatting onSave or globally because
 * SQL formatting is much more opinionated than Python formatting, and we
 * don't want to tie the two together (just yet).
 */
export async function formatSQL(editor: EditorView) {
  // Lazy import sql-formatter
  const { formatDialect, duckdb } = await import("sql-formatter");

  // Get language adapter
  const languageAdapter = editor.state.field(languageAdapterState);
  const tabWidth = getIndentUnit(editor.state);
  if (languageAdapter.type !== "sql") {
    Logger.error("Language adapter is not SQL");
    return;
  }

  const codeAsSQL = editor.state.doc.toString();
  const formattedSQL = formatDialect(codeAsSQL, {
    dialect: duckdb,
    tabWidth: tabWidth,
    useTabs: false,
  });

  // Update Python in the notebook state
  const codeAsPython = languageAdapter.transformIn(formattedSQL)[0];
  const actions = editor.state.facet(cellActionsState);
  const cellId = editor.state.facet(cellIdState);
  actions.updateCellCode({
    cellId,
    code: codeAsPython,
    formattingChange: true,
  });

  // Update editor with formatted SQL
  const doc = editor.state.doc;

  // Noop if the code is the same
  if (doc.toString() === formattedSQL) {
    return;
  }

  editor.dispatch({
    changes: { from: 0, to: doc.length, insert: formattedSQL },
    effects: [formattingChangeEffect.of(true)],
  });
}
