/* Copyright 2024 Marimo. All rights reserved. */
import { RefObject } from "react";
import { Logger } from "../../utils/Logger";
import { CellId, HTMLCellId } from "./ids";
import { CellHandle } from "@/components/editor/Cell";
import { CellConfig } from "./types";

export function focusAndScrollCellIntoView({
  cellId,
  cell,
  config,
  codeFocus,
}: {
  cellId: CellId;
  cell: RefObject<CellHandle>;
  config: CellConfig;
  codeFocus: "top" | "bottom" | undefined;
}) {
  if (!cell) {
    return;
  }

  const element = document.getElementById(HTMLCellId.create(cellId));
  if (!element) {
    Logger.warn("scrollCellIntoView: element not found");
    return;
  }

  // If the cell's code is hidden, just focus the cell and not the editor.
  if (config.hide_code) {
    element.focus();
  } else {
    const editor = cell.current?.editorView;
    if (!editor) {
      return;
    }
    editor.focus();
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
    }
  }

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
  window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
}

export function scrollToTop() {
  window.scrollTo({ top: 0, behavior: "smooth" });
}
