/* Copyright 2026 Marimo. All rights reserved. */
import type { EditorState } from "@codemirror/state";
import { StateEffect, StateField } from "@codemirror/state";
import { type EditorView, showTooltip, type Tooltip } from "@codemirror/view";

/**
 * Effect to set (or clear, with `null`) the floating signature hint.
 */
export const setSignatureHintEffect = StateEffect.define<Tooltip | null>();

// Bound the scan so large cells stay cheap on every keystroke.
const MAX_LINES_BACK = 20;

/**
 * Whether the cursor is still inside the anchored call (just inside its `(`).
 *
 * Anchor-relative paren scan, bounded to {@link MAX_LINES_BACK} lines.
 * Good enough for hint dismissal — not a full parse (ignores strings/comments).
 */
function isCursorInsideAnchoredCall(options: {
  state: EditorState;
  anchor: number;
  head: number;
}): boolean {
  const { state, anchor, head } = options;
  if (head < anchor) {
    return false;
  }

  const headLine = state.doc.lineAt(head).number;
  const anchorLine = state.doc.lineAt(anchor).number;
  const startLine = Math.max(anchorLine, headLine - MAX_LINES_BACK + 1);
  const from = Math.max(anchor, state.doc.line(startLine).from);

  // If the anchor is outside the bounded window, assume its `(` is still open.
  const assumedOpen = from > anchor;
  let balance = assumedOpen ? 1 : 0;
  const iter = state.doc.iterRange(from, head);
  for (;;) {
    const { value, done } = iter.next();
    if (done) {
      break;
    }
    for (const char of value) {
      if (char === "(") {
        balance++;
      } else if (char === ")") {
        balance--;
        const closed = assumedOpen ? balance <= 0 : balance < 0;
        if (closed) {
          return false;
        }
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
        !isCursorInsideAnchoredCall({
          state: tr.state,
          anchor,
          head: tr.state.selection.main.head,
        })
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
