/* Copyright 2026 Marimo. All rights reserved. */

import type { createStore } from "jotai";
import { getCellEditorView } from "@/core/cells/cells";
import { type CellId, HTMLCellId } from "@/core/cells/ids";
import { scrollCellIntoView } from "@/core/cells/scrollCellIntoView";
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

export function focusCell(cellId: CellId, options?: FocusOptions): void {
  const element = document.getElementById(HTMLCellId.create(cellId));
  if (element) {
    tryFocus(element, options);
  } else {
    Logger.warn(`[CellFocusManager] focusCell: element not found: ${cellId}`);
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
 * Keep the focused cell in view after a layout shift, such as its code being
 * hidden again.
 */
export function keepFocusedCellInView(): void {
  raf2(() => {
    const activeElement = document.activeElement;
    if (!activeElement) {
      return;
    }
    const focusedCell = HTMLCellId.findElementThroughShadowDOMs(activeElement);
    if (!focusedCell) {
      return;
    }
    scrollCellIntoView(HTMLCellId.parse(focusedCell.id));
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

export function tryFocus(dom: HTMLElement, options?: FocusOptions) {
  try {
    dom.focus(options);
  } catch {
    Logger.warn("[CellFocusManager] element may not be focusable", dom);
  }
}
