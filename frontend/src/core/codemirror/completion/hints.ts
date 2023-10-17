/* Copyright 2023 Marimo. All rights reserved. */
import { HTMLCellId } from "@/core/model/ids";
import {
  EditorView,
  Tooltip,
  hasHoverTooltips,
  hoverTooltip,
  showTooltip,
} from "@codemirror/view";
import { Autocompleter } from "./Autocompleter";
import { Logger } from "@/utils/Logger";
import { closeCompletion } from "@codemirror/autocomplete";
import { StateField, StateEffect } from "@codemirror/state";

export function hintTooltip() {
  return [
    hoverTooltip(
      async (view, pos) => {
        const cellContainer = HTMLCellId.findElement(view.dom);
        if (!cellContainer) {
          Logger.error("Failed to find active cell.");
          return null;
        }

        const cellId = HTMLCellId.parse(cellContainer.id);

        const result = await Autocompleter.INSTANCE.request({
          pos: pos,
          query: view.state.doc.sliceString(0, pos),
          cellId: cellId,
        });

        const tooltip = Autocompleter.asHoverTooltip(pos, result);
        // Close the completion tooltips
        if (tooltip) {
          closeCompletion(view);
        }
        return tooltip ?? null;
      },
      {
        hideOnChange: true,
      }
    ),
    cursorTooltipField,
  ];
}

/**
 * Dispatch an effect that shows a tooltip
 */
export function dispatchShowTooltip(view: EditorView, tooltip: Tooltip): void {
  view.dispatch({
    effects: TooltipFromCompletionApi.of(tooltip),
  });
}

// Effect that dispatches a tooltip
const TooltipFromCompletionApi = StateEffect.define<Tooltip>();

// Field that stores the current tooltips
const cursorTooltipField = StateField.define<Tooltip[]>({
  create: () => {
    return [];
  },
  update(tooltips, tr) {
    // If the document or selection has changed, clear the tooltips
    if (tr.docChanged || tr.selection) {
      return [];
    }

    // If the effect is a tooltip, return it
    for (const effect of tr.effects) {
      if (effect.is(TooltipFromCompletionApi)) {
        return [effect.value];
      }
    }

    // Hide if hover tooltips are enabled
    if (hasHoverTooltips(tr.state)) {
      return [];
    }

    // Otherwise, return the current tooltips
    return tooltips;
  },

  provide: (field) => {
    return showTooltip.computeN([field], (state) => {
      return state.field(field);
    });
  },
});
