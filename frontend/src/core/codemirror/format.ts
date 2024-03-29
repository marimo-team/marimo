/* Copyright 2024 Marimo. All rights reserved. */
import { EditorView } from "@codemirror/view";
import { CellId } from "../cells/ids";
import { Objects } from "../../utils/objects";
import { sendFormat } from "../network/requests";
import {
  CellActions,
  getNotebook,
  notebookCellEditorViews,
} from "../cells/cells";
import {
  getEditorCodeAsPython,
  updateEditorCodeFromPython,
} from "./language/utils";
import { StateEffect } from "@codemirror/state";
import { getUserConfig } from "../config/config";
import {
  LanguageAdapters,
  languageAdapterState,
  switchLanguage,
} from "./language/extension";
import { LanguageAdapter } from "./language/types";

export const formattingChangeEffect = StateEffect.define<boolean>();

/**
 * Format the code in the editor views via the marimo server,
 * and update the editor views with the formatted code.
 */
export async function formatEditorViews(
  views: Record<CellId, EditorView>,
  updateCellCode: CellActions["updateCellCode"],
) {
  const codes = Objects.mapValues(views, (view) => getEditorCodeAsPython(view));

  const formatResponse = await sendFormat({
    codes,
    lineLength: getUserConfig().formatting.line_length,
  });

  for (const [cellId, formattedCode] of Objects.entries(formatResponse)) {
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

    updateCellCode({ cellId, code: formattedCode, formattingChange: true });
    updateEditorCodeFromPython(view, formattedCode);
  }
}

/**
 * Format all cells in the notebook.
 */
export function formatAll(updateCellCode: CellActions["updateCellCode"]) {
  const views = notebookCellEditorViews(getNotebook());
  return formatEditorViews(views, updateCellCode);
}

export function getEditorViewMode(
  editorView: EditorView | null,
): LanguageAdapter["type"] {
  if (!editorView) {
    return "python";
  }
  return editorView.state.field(languageAdapterState).type;
}

export function canToggleMarkdown(editorView: EditorView | null) {
  if (!editorView || getEditorViewMode(editorView) === "markdown") {
    return false;
  }
  return (
    LanguageAdapters.markdown().isSupported(
      getEditorCodeAsPython(editorView),
    ) || getEditorCodeAsPython(editorView).trim() === ""
  );
}

export function toggleMarkdown(
  cellId: CellId,
  editorView: EditorView,
  updateCellCode: CellActions["updateCellCode"],
) {
  // If already in markdown mode, switch to python
  if (getEditorViewMode(editorView) === "markdown") {
    switchLanguage(editorView, "python");
    return;
  }

  if (!canToggleMarkdown(editorView)) {
    return;
  }
  if (getEditorCodeAsPython(editorView).trim() === "") {
    const blankMd = 'mo.md(rf"")';
    updateCellCode({
      cellId,
      code: blankMd,
      formattingChange: true,
    });
    updateEditorCodeFromPython(editorView, blankMd);
  }
  switchLanguage(editorView, "markdown");
}
