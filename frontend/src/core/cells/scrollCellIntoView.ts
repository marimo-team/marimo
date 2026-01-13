/* Copyright 2026 Marimo. All rights reserved. */
import type { RefObject } from "react";
import {
  isAnyCellFocused,
  tryFocus,
} from "@/components/editor/navigation/focus-utils";
import type { CellHandle } from "@/components/editor/notebook-cell";
import { retryWithTimeout } from "@/utils/timeout";
import { Logger } from "../../utils/Logger";
import { scrollActiveLineIntoView } from "../codemirror/extensions";
import { goToVariableDefinition } from "../codemirror/go-to-definition/commands";
import { getCellEditorView } from "./cells";
import { type CellId, HTMLCellId } from "./ids";

export function focusAndScrollCellIntoView({
  cellId,
  cell,
  isCodeHidden,
  codeFocus,
  variableName,
}: {
  cellId: CellId;
  cell: RefObject<CellHandle | null>;
  isCodeHidden: boolean;
  codeFocus: "top" | "bottom" | undefined;
  variableName: string | undefined;
}) {
  if (!cell) {
    return;
  }

  const element = document.getElementById(HTMLCellId.create(cellId));
  if (!element) {
    Logger.warn("scrollCellIntoView: element not found");
    return;
  }

  // If another cell is focus at the cell level (not within or at the editor),
  // then just focus on the next cell at the same level.
  if (isAnyCellFocused()) {
    tryFocus(element);
    return;
  }

  // If the cell's code is hidden, just focus the cell and not the editor.
  if (isCodeHidden) {
    // Focus the parent element, as this is the one with the event handlers.
    // https://github.com/marimo-team/marimo/issues/2940
    tryFocus(element);
  } else {
    const editor = cell.current?.editorView;
    if (!editor) {
      Logger.warn("scrollCellIntoView: editor not found", cellId);
      return;
    }
    // Skip auto-focus if already focused, or if the document doesn't have
    // focus to avoid stealing focus from outside (e.g., when embedded in an iframe)
    if (editor.hasFocus || !document.hasFocus()) {
      return;
    }

    // Try to focus a few times
    retryWithTimeout(
      () => {
        editor.focus();
        return editor.hasFocus;
      },
      {
        retries: 5,
        delay: 20,
      },
    );

    if (codeFocus === "top") {
      // If codeFocus is top, move the cursor to the top of the editor.
      editor.dispatch({
        selection: {
          anchor: 0,
          head: 0,
        },
      });
    } else if (codeFocus === "bottom") {
      // If codeFocus is bottom, move the cursor to the bottom of the editor,
      // but front of the last line.
      const lastLine = editor.state.doc.line(editor.state.doc.lines);
      editor.dispatch({
        selection: {
          anchor: lastLine.from,
          head: lastLine.from,
        },
      });
    } else if (variableName) {
      goToVariableDefinition(editor, variableName);
    }
  }

  element.scrollIntoView({
    behavior: "smooth",
    block: "nearest",
  });
}

export function focusAndScrollCellOutputIntoView(cellId: CellId) {
  const element = document.getElementById(HTMLCellId.create(cellId));
  if (!element) {
    Logger.warn("scrollCellIntoView: element not found");
    return;
  }

  element.classList.add("focus-outline");
  setTimeout(() => {
    element.classList.remove("focus-outline");
  }, 2000);

  element.scrollIntoView({
    behavior: "smooth",
    block: "center",
  });
}

/**
 * Scroll to bottom and top of page.
 *
 * On pages with many cells, scrolling to a cell that is not in the viewport
 * can have unreliable results (cell may not yet be rendered). Scrolling
 * manually to the bottom/top is reliable.
 */
export function scrollToBottom() {
  const app = document.getElementById("App");
  app?.scrollTo({ top: app.scrollHeight, behavior: "smooth" });
}

export function scrollToTop() {
  const app = document.getElementById("App");
  app?.scrollTo({ top: 0, behavior: "smooth" });
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
