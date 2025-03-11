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
