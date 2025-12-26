/* Copyright 2026 Marimo. All rights reserved. */
import type { Extension } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { insertImage, insertTextFile } from "../markdown/commands";

export function dndBundle(): Extension[] {
  return [
    EditorView.domEventHandlers({
      drop: (event: DragEvent, view: EditorView) => {
        // Handle files
        const file = event.dataTransfer?.files[0];
        if (file?.type.startsWith("text/")) {
          event.preventDefault();
          void insertTextFile(view, file);
          return true;
        }

        if (file?.type.startsWith("image/")) {
          event.preventDefault();
          void insertImage(view, file);
          return true;
        }

        // Handle plain text
        const text = event.dataTransfer?.getData("text/plain");
        if (text) {
          event.preventDefault();
          const pos = view.posAtCoords({
            x: event.clientX,
            y: event.clientY,
          });
          if (pos !== null) {
            view.dispatch({
              changes: { from: pos, to: pos, insert: text },
              scrollIntoView: true,
            });
          }
          return true;
        }

        return false;
      },
      dragover: (event: DragEvent) => {
        event.preventDefault();
      },
    }),
  ];
}
