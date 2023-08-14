/* Copyright 2023 Marimo. All rights reserved. */
import { EditorView } from "codemirror";
import { CellId } from "../model/ids";
import { Objects } from "../../utils/objects";
import { sendFormat } from "../network/requests";

/**
 * Format the code in the editor views via the marimo server,
 * and update the editor views with the formatted code.
 */
export async function formatEditorViews(
  views: Record<CellId, EditorView>,
  updateCellCode: (
    cellId: CellId,
    code: string,
    formattingChange: boolean
  ) => void
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

    updateCellCode(cellId, formattedCode, true);

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
