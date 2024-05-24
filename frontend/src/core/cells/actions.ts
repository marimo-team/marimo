/* Copyright 2024 Marimo. All rights reserved. */

import { store } from "../state/jotai";
import { Objects } from "@/utils/objects";
import { notebookAtom } from "./cells";
import { scrollAndHighlightCell } from "@/components/editor/links/cell-link";

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
