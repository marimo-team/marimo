/* Copyright 2024 Marimo. All rights reserved. */
import type { Extension } from "@codemirror/state";
import { EditorView, keymap, placeholder } from "@codemirror/view";

/**
 * A placeholder that will be shown when the editor is empty and support
 * auto-complete on right arrow or Tab.
 */
export function smartPlaceholderExtension(text: string): Extension[] {
  return [
    placeholder(text),
    keymap.of([
      {
        key: "ArrowRight",
        preventDefault: true,
        run: (cm) => acceptPlaceholder(cm, text),
      },
      {
        key: "Tab",
        preventDefault: true,
        run: (cm) => acceptPlaceholder(cm, text),
      },
    ]),
  ];
}

function acceptPlaceholder(cm: EditorView, text: string) {
  // if empty, insert the placeholder
  if (cm.state.doc.length === 0) {
    const docLength = cm.state.doc.length;
    cm.dispatch({
      changes: {
        from: 0,
        to: docLength,
        insert: text,
      },
    });
    // move cursor to end of placeholder
    cm.dispatch({
      selection: {
        anchor: docLength,
        head: docLength,
      },
    });
    return true;
  }
  return false;
}

/**
 * Create a placeholder with a clickable link.
 */
export function clickablePlaceholderExtension(opts: {
  beforeText: string;
  linkText: string;
  afterText: string;
  onClick: (ev: EditorView) => void;
}): Extension[] {
  const { beforeText, linkText, afterText, onClick } = opts;

  // Create a placeholder
  // Needs to be a function to keep event listeners
  // See https://github.com/codemirror/dev/issues/1457
  const createPlaceholder = (ev: EditorView) => {
    const placeholderText = document.createElement("span");
    placeholderText.append(document.createTextNode(beforeText));
    const link = document.createElement("span");
    link.textContent = linkText;
    link.classList.add("cm-clickable-placeholder");
    link.onclick = (evt) => {
      evt.stopPropagation();
      onClick(ev);
    };
    placeholderText.append(link);
    placeholderText.append(document.createTextNode(afterText));
    return placeholderText;
  };

  return [
    placeholder(createPlaceholder),
    EditorView.theme({
      ".cm-placeholder": {
        color: "var(--slate-8)",
      },
      ".cm-clickable-placeholder": {
        cursor: "pointer !important",
        pointerEvents: "auto",
        color: "var(--slate-9)",
        textDecoration: "underline",
        textUnderlineOffset: "0.2em",
      },
      ".cm-clickable-placeholder:hover": {
        color: "var(--sky-11)",
      },
    }),
  ];
}
