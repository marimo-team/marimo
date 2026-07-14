/* Copyright 2026 Marimo. All rights reserved. */
import type { EditorState } from "@codemirror/state";
import { StateEffect, StateField } from "@codemirror/state";
import { type EditorView, showTooltip, type Tooltip } from "@codemirror/view";

/**
 * Effect to set (or clear, with `null`) the floating signature hint.
 */
export const setSignatureHintEffect = StateEffect.define<Tooltip | null>();

/**
 * Whether the cursor at `head` is still inside the call the hint is anchored to.
 *
 * The hint's `anchor` sits just inside the call's `(` (the position where the
 * completion fired). We scan forward from the anchor to the cursor and treat
 * the call as closed once the parenthesis balance drops below zero — i.e. the
 * anchoring `(` has been matched by a `)`. Being anchor-relative means grouping
 * parens around the call (e.g. `(plt.plot())`) don't keep a stale hint alive:
 * we dismiss exactly when *this* call closes, not when the outermost one does.
 *
 * This is a cheap character scan that does not distinguish parens inside strings
 * or comments (e.g. `f(")")`); that's acceptable because the only consumer is
 * hint dismissal, where the worst case is the hint clearing one keystroke early
 * and self-correcting on the next edit. A syntax-tree-aware check would be more
 * correct but far more expensive to run on every keystroke.
 */
function isCursorInsideAnchoredCall(
  state: EditorState,
  anchor: number,
  head: number,
): boolean {
  // Cursor moved before the call's opening paren: no longer inside it.
  if (head < anchor) {
    return false;
  }
  const text = state.doc.sliceString(anchor, head);
  let balance = 0;
  for (const char of text) {
    if (char === "(") {
      balance++;
    } else if (char === ")") {
      balance--;
      if (balance < 0) {
        return false;
      }
    }
  }
  return true;
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
 * The LSP path has its own signature help; this fills the gap for users without a language server.
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
    // Dismiss once the cursor leaves the anchored call (e.g. the closing paren
    // is typed). Otherwise keep the hint anchored across edits so it doesn't
    // flicker while a fresh result is in flight; the completion source refreshes
    // or clears it as results arrive.
    if (tr.docChanged) {
      const anchor = tr.changes.mapPos(tooltip.pos);
      if (
        !isCursorInsideAnchoredCall(
          tr.state,
          anchor,
          tr.state.selection.main.head,
        )
      ) {
        return null;
      }
      return { ...tooltip, pos: anchor };
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
