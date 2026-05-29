/* Copyright 2026 Marimo. All rights reserved. */

import { scrollAndHighlightCell } from "@/components/editor/links/cell-link";
import { store } from "../state/jotai";
import { notebookAtom } from "./cells";

/**
 * Scroll to the first cell that is currently in "running" state.
 */
export function notebookScrollToRunning() {
  // find cell that is currently in "running" state
  const { cellIds, cellRuntime } = store.get(notebookAtom);
  const cellId = cellIds.inOrderIds.find(
    (id) => cellRuntime[id]?.status === "running",
  );
  if (!cellId) {
    return;
  }
  scrollAndHighlightCell(cellId, "focus");
}
