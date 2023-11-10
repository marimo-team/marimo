/* Copyright 2023 Marimo. All rights reserved. */
import { HTMLCellId } from "@/core/cells/ids";
import {
  EditorView,
  Tooltip,
  hasHoverTooltips,
  hoverTooltip,
  keymap,
  showTooltip,
} from "@codemirror/view";
import { AUTOCOMPLETER, Autocompleter } from "./Autocompleter";
import { Logger } from "@/utils/Logger";
import { StateField, StateEffect, Prec, Text } from "@codemirror/state";

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

        const { startToken, endToken } = getPositionAtWordBounds(
          view.state.doc,
          pos
        );

        const result = await AUTOCOMPLETER.request({
          document: view.state.doc.slice(0, endToken).toString(), // convert Text to string
          cellId: cellId,
        });

        const fullWord = view.state.doc.slice(startToken, endToken).toString();
        const tooltip = Autocompleter.asHoverTooltip({
          position: endToken,
          message: result,
          exactName: fullWord,
          excludeTypes: ["tooltip"],
        });
        return tooltip ?? null;
      },
      {
        hideOnChange: true,
      }
    ),
    cursorTooltipField,
    Prec.highest(
      keymap.of([
        {
          key: "Escape",
          run: clearTooltips,
        },
      ])
    ),
    Prec.highest(
      keymap.of([
        {
          key: "Backspace",
          run: (view) => {
            clearTooltips(view);
            return false; // don't stop propagation
          },
        },
      ])
    ),
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
export function dispatchShowTooltip(
  view: EditorView,
  tooltip: Tooltip | undefined
): void {
  view.dispatch({
    effects: TooltipFromCompletionApi.of([tooltip].filter(Boolean)),
  });
}

export function clearTooltips(view: EditorView): boolean {
  const hasCompletionTooltip = view.state.field(cursorTooltipField).length > 0;
  if (hasCompletionTooltip) {
    view.dispatch({
      effects: TooltipFromCompletionApi.of([]),
    });
    return true;
  }
  return false;
}

// Effect that dispatches a tooltip
const TooltipFromCompletionApi = StateEffect.define<Tooltip[]>();

// Field that stores the current tooltips
const cursorTooltipField = StateField.define<Tooltip[]>({
  create: () => {
    return [];
  },
  update(tooltips, tr) {
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

export function getPositionAtWordBounds(doc: Text, pos: number) {
  let startToken = pos;
  let endToken = pos;

  // Start of word
  while (startToken > 0) {
    const prevChar = doc.sliceString(startToken - 1, startToken);
    // Anything but a letter, number, or underscore
    if (!/\w/.test(prevChar)) {
      break;
    }
    startToken--;
  }

  // End of word
  while (endToken < doc.length) {
    const nextChar = doc.sliceString(endToken, endToken + 1);
    // Anything but a letter, number, or underscore
    if (!/\w/.test(nextChar)) {
      break;
    }
    endToken++;
  }

  return { startToken, endToken };
}
