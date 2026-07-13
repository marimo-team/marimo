/* Copyright 2026 Marimo. All rights reserved. */
import type { EditorState } from "@codemirror/state";
import { StateEffect, StateField } from "@codemirror/state";
import { type EditorView, showTooltip, type Tooltip } from "@codemirror/view";

/**
 * Effect to set (or clear, with `null`) the floating signature hint.
 */
export const setSignatureHintEffect = StateEffect.define<Tooltip | null>();

// Bound the backward scan so large cells stay cheap on every keystroke.
const MAX_LINES_BACK = 20;

/**
 * Cheap heuristic for whether `pos` sits inside an unclosed call, by counting
 * raw parentheses balance over the preceding (bounded) lines. Mirrors the LSP
 * path's `isCursorInsideFunctionCall`.
 *
 * This does NOT distinguish parens inside strings or comments (e.g. `f(")")`),
 * and it only scans back `MAX_LINES_BACK` lines. That's acceptable because the
 * sole consumer is hint dismissal: the worst case is the hint lingering or
 * clearing slightly early in a rare edge case, and it self-corrects on the next
 * edit or cursor move. A syntax-tree-aware check would be more correct but far
 * more expensive to run on every keystroke.
 */
function isCursorInsideCall(state: EditorState, pos: number): boolean {
  const line = state.doc.lineAt(pos);
  const startLine = Math.max(1, line.number - MAX_LINES_BACK);
  const from = state.doc.line(startLine).from;
  const text = state.doc.sliceString(from, pos);
  let balance = 0;
  for (const char of text) {
    if (char === "(") {
      balance++;
    } else if (char === ")") {
      balance--;
    }
  }
  return balance > 0;
}

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
    // Dismiss once the cursor leaves the call. Otherwise keep the
    // hint anchored across edits so it doesn't flicker while a fresh result is
    // in flight; the completion source refreshes or clears it as results arrive.
    if (tr.docChanged) {
      if (!isCursorInsideCall(tr.state, tr.state.selection.main.head)) {
        return null;
      }
      return { ...tooltip, pos: tr.changes.mapPos(tooltip.pos) };
    }
    return tooltip;
  },
  provide: (field) => showTooltip.from(field),
});

/**
 * Dismiss the floating signature hint if one is showing.
 * Returns `true` if a hint was dismissed.
 */
export function closeSignatureHint(view: EditorView): boolean {
  if (view.state.field(signatureHintField, false)) {
    view.dispatch({ effects: setSignatureHintEffect.of(null) });
    return true;
  }
  return false;
}
