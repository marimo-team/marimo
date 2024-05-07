/* Copyright 2024 Marimo. All rights reserved. */

import { store } from "../state/jotai";
import { Objects } from "@/utils/objects";
import { EditorView } from "@codemirror/view";
import { getCellEditorView, notebookAtom } from "./cells";

/**
 * Scroll to the first cell that is currently in "running" state.
 */
export function notebookScrollToRunning() {
  // find cell that is currently in "running" state
  const { cellRuntime } = store.get(notebookAtom);
  const cell = Objects.entries(cellRuntime).find(
    ([cellid, runtimestate]) => runtimestate.status === "running",
  );
  if (!cell) {
    return;
  }
  const view = getCellEditorView(cell[0]);
  view?.dispatch({
    selection: { anchor: 0 },
    effects: [EditorView.scrollIntoView(0, { y: "center" })],
  });
}
