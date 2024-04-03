/* Copyright 2024 Marimo. All rights reserved. */
import { Extension } from "@codemirror/state";
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
    cm.dispatch({
      changes: {
        from: 0,
        to: cm.state.doc.length,
        insert: text,
      },
    });
    // move cursor to end of placeholder
    cm.dispatch({
      selection: {
        anchor: cm.state.doc.length,
        head: cm.state.doc.length,
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
  onClick: () => void;
}): Extension[] {
  const { beforeText, linkText, afterText, onClick } = opts;

  // Create a placeholder
  const placeholderText = document.createElement("span");
  placeholderText.append(document.createTextNode(beforeText));
  const link = document.createElement("span");
  link.textContent = linkText;
  link.classList.add("cm-clickable-placeholder");
  link.onclick = (evt) => {
    evt.stopPropagation();
    onClick();
  };
  placeholderText.append(link);
  placeholderText.append(document.createTextNode(afterText));

  return [
    placeholder(placeholderText),
    EditorView.theme({
      ".cm-clickable-placeholder": {
        cursor: "pointer !important",
        pointerEvents: "auto",
        color: "var(--slate-10)",
        textDecoration: "underline",
        textDecorationThickness: "0.1em",
        textUnderlineOffset: "0.2em",
      },
      ".cm-clickable-placeholder:hover": {
        color: "var(--sky-11)",
      },
    }),
  ];
}
