/* Copyright 2026 Marimo. All rights reserved. */
import type { Cell, RowData, Table } from "@tanstack/react-table";
import {
  type ReactNode,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
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
}: {
  table: Table<TData>;
}) {
  const hoverTemplate = table.getState().cellHoverTemplate || null;
  const [tooltipState, setTooltipState] = useState<HoverTooltipState | null>(
    null,
  );
  const timer = useRef<number | null>(null);

  // Stable id linking the focused/hovered cell to the tooltip content for
  // assistive tech (the radix trigger is an aria-hidden phantom anchor).
  const tooltipContentId = useId();
  const anchorCell = useRef<HTMLElement | null>(null);

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
    anchorCell.current = target;
    const r = target.getBoundingClientRect();
    setTooltipState({
      rect: { top: r.top, left: r.left, width: r.width, height: r.height },
      content,
    });
  };

  // Point the real cell at the tooltip content while it is shown. Done in a
  // layout effect (after commit) so React's re-render from `setTooltipState`
  // can't clobber an imperatively set attribute; cleanup unlinks the previous
  // cell.
  useLayoutEffect(() => {
    if (!tooltipState) {
      return;
    }
    const cell = anchorCell.current;
    cell?.setAttribute("aria-describedby", tooltipContentId);
    return () => cell?.removeAttribute("aria-describedby");
  }, [tooltipState, tooltipContentId]);

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
      // Cancel any pending hover-show so a stale timer can't overwrite the
      // focus-triggered tooltip after the delay.
      clearTimer();
      const content = computeCellTooltipContent(cell, hoverTemplate);
      if (content == null || content === "") {
        return;
      }
      showFor(e.currentTarget as HTMLElement, content);
    },
  );

  const handleCellBlur = useEvent(() => hideTooltip());

  // The anchor rect is captured at hover time, so any scroll or resize leaves
  // it stale; hide instead of tracking. Capture catches scrolls inside the
  // table's own container too (scroll events don't bubble but do fire in
  // capture).
  useEffect(() => {
    const opts = { passive: true, capture: true } as const;
    window.addEventListener("scroll", hideTooltip, opts);
    window.addEventListener("resize", hideTooltip);
    return () => {
      window.removeEventListener("scroll", hideTooltip, { capture: true });
      window.removeEventListener("resize", hideTooltip);
    };
  }, [hideTooltip]);

  useEffect(() => clearTimer, []);

  return {
    tooltipState,
    tooltipContentId,
    hideTooltip,
    handleCellMouseOver,
    handleCellMouseLeave,
    handleCellFocus,
    handleCellBlur,
  };
}
