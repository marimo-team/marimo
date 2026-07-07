/* Copyright 2026 Marimo. All rights reserved. */
import { StateEffect, StateField } from "@codemirror/state";
import { showTooltip, type Tooltip } from "@codemirror/view";

/**
 * Effect to set (or clear, with `null`) the floating signature hint.
 */
export const setSignatureHintEffect = StateEffect.define<Tooltip | null>();

/**
 * Wrap a tooltip so it renders like the completion popup's info box.
 *
 * CodeMirror adds `cm-tooltip` directly to the DOM node returned by `create`,
 * so the documentation content ends up on the same element as `cm-tooltip`.
 * Our styling for padding/font (`.cm-tooltip .docs-documentation`) is a
 * descendant selector, so we nest the content one level deeper to make it
 * apply — mirroring how CodeMirror nests completion info inside its own
 * wrapper. The outer `mo-cm-tooltip` class picks up the shared tooltip sizing.
 */
export function asSignatureHint(tooltip: Tooltip): Tooltip {
  return {
    ...tooltip,
    create: (view) => {
      const { dom: content, ...rest } = tooltip.create(view);
      const dom = document.createElement("div");
      dom.classList.add("mo-cm-tooltip");
      dom.append(content);
      return { ...rest, dom };
    },
  };
}

/**
 * Holds the floating "signature hint" shown after typing `(` or `,` inside a
 * call on the non-LSP (Jedi) completion path.
 *
 * The LSP path has its own signature help; this fills the gap for users
 * without a language server. The completion source (`pythonCompletionSource`)
 * drives it: it dispatches `setSignatureHintEffect` with the tooltip when the
 * backend returns a signature and with `null` otherwise. The hint is also
 * cleared when the cursor moves via a selection-only change (e.g. clicking
 * away or arrowing out of the call), and kept anchored across edits so it
 * doesn't flicker while a fresh result is in flight.
 */
export const signatureHintField = StateField.define<Tooltip | null>({
  create: () => null,
  update(tooltip, tr) {
    for (const effect of tr.effects) {
      if (effect.is(setSignatureHintEffect)) {
        return effect.value;
      }
    }
    if (!tooltip) {
      return null;
    }
    // Cursor moved without editing (click / arrow key): dismiss the hint.
    if (tr.selection && !tr.docChanged) {
      return null;
    }
    // Keep the hint anchored across edits; the completion source refreshes or
    // clears it as new results arrive.
    if (tr.docChanged) {
      return { ...tooltip, pos: tr.changes.mapPos(tooltip.pos) };
    }
    return tooltip;
  },
  provide: (field) => showTooltip.from(field),
});
