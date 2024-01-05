/* Copyright 2023 Marimo. All rights reserved. */
import { RefObject } from "react";
import { Logger } from "../../utils/Logger";
import { CellId, HTMLCellId } from "./ids";
import { CellHandle } from "@/components/editor/Cell";
import { CellConfig } from "./types";

export function focusAndScrollCellIntoView(
  cellId: CellId,
  cell: RefObject<CellHandle>,
  config: CellConfig
) {
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
    cell.current?.editorView.focus();
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
