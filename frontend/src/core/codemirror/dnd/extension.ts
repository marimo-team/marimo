/* Copyright 2024 Marimo. All rights reserved. */
import { Extension } from "@codemirror/state";
import { EditorView } from "@codemirror/view";

export function dndBundle(): Extension {
  return [
    EditorView.domEventHandlers({
      drop: (event: DragEvent, view: EditorView) => {
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
        }
      },
      dragover: (event: DragEvent) => {
        event.preventDefault();
      },
    }),
  ];
}
