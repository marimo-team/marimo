/* Copyright 2024 Marimo. All rights reserved. */

import { atom } from "jotai";
import { useJotaiEffect } from "@/core/state/jotai";
import { Logger } from "@/utils/Logger";
import { cellSelectionStateAtom } from "./atoms";

const focusedCellAtom = atom((get) => get(cellSelectionStateAtom).focusedCell);

/**
 * Hook that automatically scrolls the focused cell into view when it changes.
 * This ensures that when users navigate with keyboard or select cells,
 * the focused cell remains visible in scrollable tables.
 */
export function useScrollIntoViewOnFocus(
  root: React.RefObject<HTMLElement | null>,
) {
  useJotaiEffect(focusedCellAtom, (focusedCell) => {
    if (!focusedCell?.cellId) {
      return;
    }

    const scroll = () => {
      // Check if this cell contains the CellRangeSelectionIndicator with our cellId
      const indicator = root.current?.querySelector(
        `[data-cell-id="${focusedCell.cellId}"]`,
      );
      if (!indicator) {
        Logger.warn(
          "[ScrollIntoView] Could not find cell with ID:",
          focusedCell.cellId,
        );
        return;
      }

      indicator.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
        inline: "nearest",
      });
    };

    // Small delay to ensure DOM updates have completed
    setTimeout(scroll, 0);
  });
}
