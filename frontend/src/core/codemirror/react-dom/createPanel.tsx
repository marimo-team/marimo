/* Copyright 2024 Marimo. All rights reserved. */
import { EditorView, Panel, ViewUpdate } from "@codemirror/view";
import { Root, createRoot } from "react-dom/client";

export function createPanel(view: ViewUpdate | EditorView, Component: React.ComponentType<{view: ViewUpdate | EditorView}>): Panel {
  const dom = document.createElement("div");
  let root: Root | undefined;

  return {
    dom,
    mount() {
      root = createRoot(dom);
      root.render(<Component view={view}/>);
    },
    update(view) {
      root?.render(<Component view={view}/>);
    },
    destroy() {
      root?.unmount();
    },
  }
}
