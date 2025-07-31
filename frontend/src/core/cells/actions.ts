/* Copyright 2024 Marimo. All rights reserved. */

import { scrollAndHighlightCell } from "@/components/editor/links/cell-link";
import { Objects } from "@/utils/objects";
import { store } from "../state/jotai";
import { notebookAtom } from "./cells";

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
  scrollAndHighlightCell(cell[0], "focus");
}
