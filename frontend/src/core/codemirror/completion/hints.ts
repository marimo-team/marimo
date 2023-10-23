/* Copyright 2023 Marimo. All rights reserved. */
import { HTMLCellId } from "@/core/model/ids";
import {
  EditorView,
  Tooltip,
  hasHoverTooltips,
  hoverTooltip,
  showTooltip,
} from "@codemirror/view";
import { AUTOCOMPLETER, Autocompleter } from "./Autocompleter";
import { Logger } from "@/utils/Logger";
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

        let startToken = pos;
        let endToken = pos;

        // Start of word
        while (startToken > 0) {
          const prevChar = view.state.doc.sliceString(
            startToken - 1,
            startToken
          );
          // Anything but a letter or number
          if (!/[\dA-Za-z]/.test(prevChar)) {
            break;
          }
          startToken--;
        }

        // End of word
        while (endToken < view.state.doc.length) {
          const nextChar = view.state.doc.sliceString(endToken, endToken + 1);
          // Anything but a letter or number
          if (!/[\dA-Za-z]/.test(nextChar)) {
            break;
          }
          endToken++;
        }

        const result = await AUTOCOMPLETER.request({
          document: view.state.doc.slice(0, endToken).toString(), // convert Text to string
          cellId: cellId,
        });

        const fullWord = view.state.doc.slice(startToken, endToken).toString();
        const tooltip = Autocompleter.asHoverTooltip({
          position: endToken,
          message: result,
          exactName: fullWord,
        });
        return tooltip ?? null;
      },
      {
        hideOnChange: true,
      }
    ),
    cursorTooltipField,
    // Clear tooltips on blur
    EditorView.domEventObservers({
      blur: (event, view) => {
        // Only close tooltip, not view; blur for completion handled by
        // cell editor, so that completion text is selectable
        clearTooltips(view);
      },
    }),
  ];
}

/**
 * Dispatch an effect that shows a tooltip
 */
export function dispatchShowTooltip(view: EditorView, tooltip: Tooltip): void {
  view.dispatch({
    effects: TooltipFromCompletionApi.of([tooltip]),
  });
}

function clearTooltips(view: EditorView): void {
  view.dispatch({
    effects: TooltipFromCompletionApi.of([]),
  });
}

// Effect that dispatches a tooltip
const TooltipFromCompletionApi = StateEffect.define<Tooltip[]>();

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
        return effect.value;
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
