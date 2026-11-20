/* Copyright 2026 Marimo. All rights reserved. */
import type { Extension } from "@codemirror/state";
import {
  Decoration,
  EditorView,
  keymap,
  placeholder,
  WidgetType,
} from "@codemirror/view";
import { isEditorReadonly } from "../readonly/extension";

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
  if (isEditorReadonly(cm.state)) {
    return false;
  }

  // if empty, insert the placeholder
  const docLength = cm.state.doc.length;
  if (docLength === 0) {
    cm.dispatch({
      changes: {
        from: 0,
        to: docLength,
        insert: text,
      },
      selection: {
        head: text.length,
        anchor: text.length,
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

  class ActionPlaceholder extends WidgetType {
    public toDOM(ev: EditorView) {
      const wrapper = document.createElement("span");
      wrapper.className = "cm-placeholder";
      wrapper.contentEditable = "false";
      const before = document.createElement("span");
      before.textContent = beforeText;
      before.setAttribute("aria-hidden", "true");
      wrapper.append(before);
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = linkText;
      button.className = "cm-clickable-placeholder";
      button.onclick = (event) => {
        event.stopPropagation();
        onClick(ev);
      };
      const after = document.createElement("span");
      after.textContent = afterText;
      after.setAttribute("aria-hidden", "true");
      wrapper.append(button, after);
      return wrapper;
    }

    public override coordsAt(dom: HTMLElement) {
      // A wrapped placeholder must not make the caret span every line.
      const walker = document.createTreeWalker(dom, NodeFilter.SHOW_TEXT);
      let text = walker.nextNode();
      while (text && !text.textContent) {
        text = walker.nextNode();
      }
      if (!text) {
        return null;
      }
      const range = document.createRange();
      range.selectNodeContents(text);
      const rect = range.getClientRects()[0];
      if (!rect) {
        return null;
      }
      const left =
        window.getComputedStyle(dom).direction === "rtl"
          ? rect.right
          : rect.left;
      return { left, right: left, top: rect.top, bottom: rect.bottom };
    }

    public override ignoreEvent(event: Event) {
      return (
        event.target instanceof Element &&
        event.target.closest(".cm-clickable-placeholder") !== null
      );
    }
  }

  return [
    EditorView.decorations.compute(["doc"], (state) =>
      state.doc.length === 0
        ? Decoration.set([
            Decoration.widget({
              widget: new ActionPlaceholder(),
              side: 1,
            }).range(0),
          ])
        : Decoration.none,
    ),
    EditorView.theme({
      ".cm-placeholder": {
        color: "var(--slate-8)",
      },
      ".cm-clickable-placeholder": {
        cursor: "pointer !important",
        font: "inherit",
        background: "transparent",
        border: "none",
        padding: "0",
        pointerEvents: "auto",
        color: "var(--slate-9)",
        textDecoration: "underline",
        textUnderlineOffset: "0.2em",
      },
      ".cm-clickable-placeholder:focus-visible": {
        outline: "1px solid var(--muted-foreground)",
        outlineOffset: "2px",
        borderRadius: "2px",
      },
      ".cm-clickable-placeholder:hover": {
        color: "var(--sky-11)",
      },
    }),
  ];
}
