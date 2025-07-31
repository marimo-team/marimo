/* Copyright 2024 Marimo. All rights reserved. */

import type { EditorView, Panel } from "@codemirror/view";
import { Provider } from "jotai";
import { createRoot, type Root } from "react-dom/client";
import { store } from "@/core/state/jotai";

/**
 * Bridge between Codemirror panels and React
 */
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
      root.render(
        <Provider store={store}>
          <Component view={view} />
        </Provider>,
      );
    },
    update() {
      root?.render(
        <Provider store={store}>
          <Component view={view} />
        </Provider>,
      );
    },
    destroy() {
      root?.unmount();
    },
  };
}
