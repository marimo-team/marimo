/* Copyright 2023 Marimo. All rights reserved. */
import { CompletionContext, CompletionResult } from "@codemirror/autocomplete";

import { Autocompleter } from "./Autocompleter";
import { Logger } from "../../../utils/Logger";
import { CellId, HTMLCellId } from "@/core/model/ids";
import { getCells } from "@/core/state/cells";
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

  const result = await Autocompleter.INSTANCE.request({
    pos: context.pos,
    query: query,
    cellId: cellId,
  });

  // If it is a tooltip, show it as a Tooltip instead of a completion
  const tooltip = Autocompleter.asHoverTooltip({
    position: context.pos,
    message: result,
    limitToType: "tooltip",
  });
  if (tooltip) {
    // Find EditorView for the cell
    const editorView = getCells().find((cell) => cell.key === cellId)?.ref
      .current?.editorView;
    if (editorView) {
      dispatchShowTooltip(editorView, tooltip);
    }
    return null;
  }

  return Autocompleter.asCompletionResult(context.pos, result);
}
