/* Copyright 2026 Marimo. All rights reserved. */
import type { Cell, RowData, Table } from "@tanstack/react-table";
import { type ReactNode, useEffect, useRef, useState } from "react";
import useEvent from "react-use-event-hook";
import { computeCellTooltipContent } from "./content";

// Matches the default TooltipProvider delay (MarimoApp.tsx) for visual parity
// with the rest of the app's tooltips.
const TOOLTIP_DELAY_MS = 400;

export interface HoverTooltipState {
  rect: { top: number; left: number; width: number; height: number };
  content: ReactNode;
}

export function useTableHoverTooltip<TData extends RowData>({
  table,
  scrollElement,
}: {
  table: Table<TData>;
  scrollElement: HTMLElement | null;
}) {
  const hoverTemplate = table.getState().cellHoverTemplate || null;
  const [tooltipState, setTooltipState] = useState<HoverTooltipState | null>(
    null,
  );
  const timer = useRef<number | null>(null);

  const clearTimer = () => {
    if (timer.current != null) {
      clearTimeout(timer.current);
      timer.current = null;
    }
  };

  const hideTooltip = useEvent(() => {
    clearTimer();
    setTooltipState(null);
  });

  const showFor = (target: HTMLElement, content: ReactNode) => {
    const r = target.getBoundingClientRect();
    setTooltipState({
      rect: { top: r.top, left: r.left, width: r.width, height: r.height },
      content,
    });
  };

  const handleCellMouseOver = useEvent(
    (e: React.MouseEvent, cell: Cell<TData, unknown>) => {
      // Suppress while a mouse button is held (range-select drag).
      if (e.buttons !== 0) {
        return;
      }
      const target = e.currentTarget as HTMLElement;
      const content = computeCellTooltipContent(cell, hoverTemplate);
      if (content == null || content === "") {
        hideTooltip();
        return;
      }
      clearTimer();
      timer.current = window.setTimeout(
        () => showFor(target, content),
        TOOLTIP_DELAY_MS,
      );
    },
  );

  const handleCellMouseLeave = useEvent(() => hideTooltip());

  // Keyboard parity: cells are tabIndex=0, native `title` showed on focus too.
  const handleCellFocus = useEvent(
    (e: React.FocusEvent, cell: Cell<TData, unknown>) => {
      const content = computeCellTooltipContent(cell, hoverTemplate);
      if (content == null || content === "") {
        return;
      }
      showFor(e.currentTarget as HTMLElement, content);
    },
  );

  const handleCellBlur = useEvent(() => hideTooltip());

  // The anchor rect is captured at hover time, so scrolling would leave it
  // stale; hide instead of trying to track.
  useEffect(() => {
    if (!scrollElement) {
      return;
    }
    scrollElement.addEventListener("scroll", hideTooltip, { passive: true });
    return () => scrollElement.removeEventListener("scroll", hideTooltip);
  }, [scrollElement, hideTooltip]);

  useEffect(() => clearTimer, []);

  return {
    tooltipState,
    hideTooltip,
    handleCellMouseOver,
    handleCellMouseLeave,
    handleCellFocus,
    handleCellBlur,
  };
}
