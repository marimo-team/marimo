/* Copyright 2024 Marimo. All rights reserved. */

import { type createStore, useStore } from "jotai";
import { notebookAtom } from "@/core/cells/cells";
import { type CellId, HTMLCellId } from "@/core/cells/ids";
import { Logger } from "@/utils/Logger";

export class CellFocusManager {
  constructor(private readonly store: ReturnType<typeof createStore>) {}

  focusCellEditor(cellId: CellId): void {
    const editor =
      this.store.get(notebookAtom).cellHandles[cellId]?.current?.editorView;
    if (editor) {
      editor.focus();
    } else {
      Logger.warn(
        `[CellFocusManager] focusCellEditor: element not found: ${cellId}`,
      );
    }
  }

  focusCell(cellId: CellId): void {
    const element = document.getElementById(HTMLCellId.create(cellId));
    if (element) {
      element.focus();
    } else {
      Logger.warn(`[CellFocusManager] focusCell: element not found: ${cellId}`);
    }
  }
}

export function useCellFocusManager() {
  const store = useStore();
  return new CellFocusManager(store);
}
