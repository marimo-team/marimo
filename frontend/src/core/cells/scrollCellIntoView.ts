/* Copyright 2023 Marimo. All rights reserved. */
import { RefObject } from "react";
import { Logger } from "../../utils/Logger";
import { CellId, HTMLCellId } from "./ids";
import { CellHandle } from "@/components/editor/Cell";

export function focusAndScrollCellIntoView(
  cellId: CellId,
  cell: RefObject<CellHandle> | undefined
) {
  if (!cell) {
    return;
  }

  cell.current?.editorView.focus();
  const element = document.getElementById(HTMLCellId.create(cellId));
  if (element) {
    element.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  } else {
    Logger.warn("scrollCellIntoView: element not found");
  }
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
