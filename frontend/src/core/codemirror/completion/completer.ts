/* Copyright 2024 Marimo. All rights reserved. */
import type {
  CompletionContext,
  CompletionResult,
  CompletionSource,
} from "@codemirror/autocomplete";
import { type CellId, HTMLCellId } from "@/core/cells/ids";
import { documentationAtom } from "@/core/documentation/state";
import { store } from "@/core/state/jotai";
import { Logger } from "../../../utils/Logger";
import { AUTOCOMPLETER, Autocompleter } from "./Autocompleter";

/**
 * Completion source for Python, using Jedi.
 */
export const pythonCompletionSource: CompletionSource = async (
  context: CompletionContext,
): Promise<CompletionResult | null> => {
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
  if (!result) {
    return null;
  }

  // If it is a tooltip, show it as a Tooltip instead of a completion
  const tooltip = Autocompleter.asHoverTooltip({
    position: context.pos,
    message: result,
    limitToType: "tooltip",
  });
  if (tooltip) {
    store.set(documentationAtom, {
      documentation: tooltip.html ?? null,
    });
  }
  if (tooltip) {
    return null;
  }

  return Autocompleter.asCompletionResult(context.pos, result);
};
