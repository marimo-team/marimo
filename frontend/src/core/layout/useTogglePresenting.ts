/* Copyright 2024 Marimo. All rights reserved. */

import { useSetAtom } from "jotai";
import { useCallback } from "react";
import { type CellId, HTMLCellId } from "../cells/ids";
import { toggleAppMode, viewStateAtom } from "../mode";

/**
 * Toggle the notebook's presentation state and scroll to current visible cell
 */
export function useTogglePresenting() {
  const setViewState = useSetAtom(viewStateAtom);

  // Toggle the array's presenting state, and sets a cell to scroll to
  const togglePresenting = useCallback(() => {
    const outputAreas = document.getElementsByClassName("output-area");
    const viewportEnd =
      window.innerHeight || document.documentElement.clientHeight;
    let cellAnchor: CellId | null = null;

    // Find the first output area that is visible
    // eslint-disable-next-line unicorn/prefer-spread
    for (const elem of Array.from(outputAreas)) {
      const rect = elem.getBoundingClientRect();
      if (
        (rect.top >= 0 && rect.top <= viewportEnd) ||
        (rect.bottom >= 0 && rect.bottom <= viewportEnd)
      ) {
        cellAnchor = HTMLCellId.parse(
          (elem.parentNode as HTMLElement).id as HTMLCellId,
        );
        break;
      }
    }

    setViewState((prev) => ({
      mode: toggleAppMode(prev.mode),
      cellAnchor: cellAnchor,
    }));

    requestAnimationFrame(() => {
      if (cellAnchor === null) {
        return;
      }
      document.getElementById(HTMLCellId.create(cellAnchor))?.scrollIntoView();
    });
  }, [setViewState]);

  return togglePresenting;
}
