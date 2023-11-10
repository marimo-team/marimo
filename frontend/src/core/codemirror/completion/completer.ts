/* Copyright 2023 Marimo. All rights reserved. */
import { CompletionContext, CompletionResult } from "@codemirror/autocomplete";

import { AUTOCOMPLETER, Autocompleter } from "./Autocompleter";
import { Logger } from "../../../utils/Logger";
import { CellId, HTMLCellId } from "@/core/cells/ids";
import { getCellEditorView } from "@/core/cells/cells";
import { dispatchShowTooltip } from "./hints";

export async function completer(
  context: CompletionContext
): Promise<CompletionResult | null> {
  const query = context.state.doc.sliceString(0, context.pos);
  const element = document.activeElement;
  let cellId: CellId | null = null;
  if (element !== null) {
    const cellContainer = HTMLCellId.findElement(element);
    if (cellContainer !== null) {
      cellId = HTMLCellId.parse(cellContainer.id);
    }
  }

  if (cellId === null) {
    Logger.error("Failed to find active cell.");
    return null;
  }

  const result = await AUTOCOMPLETER.request({
    document: query,
    cellId: cellId,
  });

  // If it is a tooltip, show it as a Tooltip instead of a completion
  const tooltip = Autocompleter.asHoverTooltip({
    position: context.pos,
    message: result,
    limitToType: "tooltip",
  });
  // Find EditorView for the cell
  const editorView = getCellEditorView(cellId);
  if (editorView) {
    dispatchShowTooltip(editorView, tooltip);
  }
  if (tooltip) {
    return null;
  }

  return Autocompleter.asCompletionResult(context.pos, result);
}
