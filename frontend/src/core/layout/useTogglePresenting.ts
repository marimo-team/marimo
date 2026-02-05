/* Copyright 2026 Marimo. All rights reserved. */

import { useSetAtom } from "jotai";
import { useCallback } from "react";
import { Logger } from "@/utils/Logger";
import { type CellId, HTMLCellId } from "../cells/ids";
import { CSSClasses } from "../constants";
import { toggleAppMode, viewStateAtom } from "../mode";

interface ScrollAnchor {
  cellId: CellId;
}

function findScrollAnchor(): ScrollAnchor | null {
  const outputAreas = document.getElementsByClassName(CSSClasses.outputArea);

  for (const elem of outputAreas) {
    const rect = elem.getBoundingClientRect();

    // Find first visible output area
    if (rect.bottom > 0 && rect.top < window.innerHeight) {
      const cellEl = HTMLCellId.findElement(elem);
      if (!cellEl) {
        Logger.warn("Could not find HTMLCellId for visible output area", elem);
        continue;
      }
      return {
        cellId: HTMLCellId.parse(cellEl.id),
      };
    }
  }

  Logger.warn("No visible output area found for scroll anchor");
  return null;
}

function restoreScrollPosition(anchor: ScrollAnchor | null): void {
  if (!anchor) {
    Logger.warn("No scroll anchor provided to restore scroll position");
    return;
  }

  // Find the cell element
  const cellElement = document.getElementById(HTMLCellId.create(anchor.cellId));
  if (!cellElement) {
    Logger.warn(
      "Could not find cell element to restore scroll position",
      anchor.cellId,
    );
    return;
  }

  // Find its output area
  const outputArea = cellElement.querySelector(`.${CSSClasses.outputArea}`);
  if (!outputArea) {
    Logger.warn(
      "Could not find output area to restore scroll position",
      anchor.cellId,
    );
    return;
  }

  // Adjust scroll to restore visual position
  cellElement.scrollIntoView({ block: "start", behavior: "auto" });
}

/**
 * Toggle the notebook's presentation state and scroll to current visible cell
 */
export function useTogglePresenting() {
  const setViewState = useSetAtom(viewStateAtom);

  // Toggle the array's presenting state and preserve scroll position
  const togglePresenting = useCallback(() => {
    // Capture scroll anchor BEFORE toggle
    const scrollAnchor = findScrollAnchor();

    // Toggle the mode
    setViewState((prev) => ({
      mode: toggleAppMode(prev.mode),
      cellAnchor: scrollAnchor?.cellId ?? null,
    }));

    // Restore scroll position AFTER DOM updates
    // Double RAF ensures React commits changes and browser completes layout
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        restoreScrollPosition(scrollAnchor);
      });
    });
  }, [setViewState]);

  return togglePresenting;
}
