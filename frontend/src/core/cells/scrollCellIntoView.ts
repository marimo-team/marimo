/* Copyright 2024 Marimo. All rights reserved. */
import type { RefObject } from "react";
import type { CellHandle } from "@/components/editor/Cell";
import {
  isAnyCellFocused,
  tryFocus,
} from "@/components/editor/focus/focus-manager";
import { retryWithTimeout } from "@/utils/timeout";
import { Logger } from "../../utils/Logger";
import { goToVariableDefinition } from "../codemirror/go-to-definition/commands";
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
    // If already focused, do nothing.
    if (editor.hasFocus) {
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
