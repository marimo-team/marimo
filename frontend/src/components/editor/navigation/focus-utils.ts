/* Copyright 2024 Marimo. All rights reserved. */

import type { createStore } from "jotai";
import { getCellEditorView } from "@/core/cells/cells";
import { type CellId, HTMLCellId } from "@/core/cells/ids";
import { scrollActiveLineIntoView } from "@/core/codemirror/extensions";
import { Logger } from "@/utils/Logger";

export function focusCellEditor(
  store: ReturnType<typeof createStore>,
  cellId: CellId,
): void {
  const editor = getCellEditorView(cellId);
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
 * First tries to scroll the active line into view, if the cell is focused.
 * If not, it scrolls the cell container into view.
 */
export function scrollCellIntoView(cellId: CellId): void {
  // Get cell editor element
  const editor = getCellEditorView(cellId);
  if (editor?.hasFocus) {
    scrollActiveLineIntoView(editor, { behavior: "instant" });
    return;
  }

  const element = document.getElementById(HTMLCellId.create(cellId));
  if (element) {
    element.scrollIntoView({ behavior: "instant", block: "nearest" });
  } else {
    Logger.warn(
      `[CellFocusManager] scrollCellIntoView: element not found: ${cellId}`,
    );
  }
}

/**
 * Run a callback after two frames.
 * It is somewhat common/safer to run code after two frames to ensure the DOM is fully rendered.
 */
export function raf2(callback: () => void): void {
  requestAnimationFrame(() => {
    requestAnimationFrame(callback);
  });
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
