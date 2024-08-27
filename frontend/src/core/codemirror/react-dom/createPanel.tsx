/* Copyright 2024 Marimo. All rights reserved. */
import type { EditorView, Panel } from "@codemirror/view";
import { type Root, createRoot } from "react-dom/client";

export function createPanel(
  view: EditorView,
  Component: React.ComponentType<{ view: EditorView }>,
): Panel {
  const dom = document.createElement("div");
  let root: Root | undefined;

  return {
    dom,
    mount() {
      root = createRoot(dom);
      root.render(<Component view={view} />);
    },
    update() {
      root?.render(<Component view={view} />);
    },
    destroy() {
      root?.unmount();
    },
  };
}
