/* Copyright 2024 Marimo. All rights reserved. */

import type { createStore } from "jotai";
import { notebookAtom } from "@/core/cells/cells";
import { type CellId, HTMLCellId } from "@/core/cells/ids";
import { Logger } from "@/utils/Logger";

export function focusCellEditor(
  store: ReturnType<typeof createStore>,
  cellId: CellId,
): void {
  const editor =
    store.get(notebookAtom).cellHandles[cellId]?.current?.editorView;
  if (editor) {
    editor.focus();
  } else {
    Logger.warn(
      `[CellFocusManager] focusCellEditor: element not found: ${cellId}`,
    );
  }
}

export function focusCell(cellId: CellId): void {
  const element = document.getElementById(HTMLCellId.create(cellId));
  if (element) {
    tryFocus(element);
  } else {
    Logger.warn(`[CellFocusManager] focusCell: element not found: ${cellId}`);
  }
}

/**
 * Checks if the cell is focused at the top level.
 */
export function isAnyCellFocused(): boolean {
  return (
    document.activeElement instanceof HTMLElement &&
    document.activeElement.classList.contains("marimo-cell")
  );
}

export function tryFocus(dom: HTMLElement) {
  try {
    dom.focus();
  } catch {
    Logger.warn("[CellFocusManager] element may not be focusable", dom);
  }
}
