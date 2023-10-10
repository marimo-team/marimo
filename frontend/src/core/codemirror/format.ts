/* Copyright 2023 Marimo. All rights reserved. */
import { EditorView } from "@codemirror/view";
import { CellId } from "../model/ids";
import { Objects } from "../../utils/objects";
import { sendFormat } from "../network/requests";
import { CellActions, getCells } from "../state/cells";

/**
 * Format the code in the editor views via the marimo server,
 * and update the editor views with the formatted code.
 */
export async function formatEditorViews(
  views: Record<CellId, EditorView>,
  updateCellCode: CellActions["updateCellCode"]
) {
  const codes = Objects.mapValues(views, (view) => view.state.doc.toString());

  const formatResponse = await sendFormat(codes);

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

    view.dispatch({
      changes: {
        from: 0,
        // overwrite the entire document
        to: view.state.doc.length,
        insert: formattedCode,
      },
    });
  }
}

/**
 * Format all cells in the notebook.
 */
export function formatAll(updateCellCode: CellActions["updateCellCode"]) {
  const cells = getCells();
  const views: Record<CellId, EditorView> = {};
  cells.forEach((cell) => {
    const editorView = cell.ref.current?.editorView;
    if (editorView) {
      views[cell.key] = editorView;
    }
  });
  return formatEditorViews(views, updateCellCode);
}
