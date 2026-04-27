/* Copyright 2026 Marimo. All rights reserved. */

import type { Cell, Table } from "@tanstack/react-table";
import useEvent from "react-use-event-hook";
import { Events } from "@/utils/events";
import { type SelectedCell, useCellSelectionReducerActions } from "./atoms";

export interface UseCellRangeSelectionProps<TData> {
  table: Table<TData>;
}

/*
 * Pure hook that provides only actions without causing re-renders.
 * Use this in components that only need to trigger actions.
 */
export const useCellRangeSelection = <TData>({
  table,
}: UseCellRangeSelectionProps<TData>) => {
  const actions = useCellSelectionReducerActions();

  const handleCopy = useEvent(() => {
    actions.handleCopy({
      table,
      onCopyComplete: () => {
        // Auto-clear after 500ms
        setTimeout(() => {
          actions.setCopiedCells(new Set());
        }, 500);
      },
    });
  });

  const updateSelection = useEvent(
    (newCell: SelectedCell, isShiftKey: boolean) => {
      actions.updateSelection({ newCell, isShiftKey, table });
    },
  );

  const navigate = useEvent(
    (
      e: React.KeyboardEvent<HTMLElement>,
      direction: "up" | "down" | "left" | "right",
    ) => {
      actions.navigate({ direction, isShiftKey: e.shiftKey, table });
    },
  );

  const handleCellsKeyDown = useEvent((e: React.KeyboardEvent<HTMLElement>) => {
    switch (e.key) {
      case "c":
        if (Events.isMetaOrCtrl(e)) {
          handleCopy();
        }
        break;
      case "ArrowDown":
        e.preventDefault();
        navigate(e, "down");
        break;
      case "ArrowUp":
        e.preventDefault();
        navigate(e, "up");
        break;
      case "ArrowLeft":
        e.preventDefault();
        navigate(e, "left");
        break;
      case "ArrowRight":
        e.preventDefault();
        navigate(e, "right");
        break;
      case "Enter":
        e.preventDefault();
        actions.toggleCurrentRowSelection(table);
        break;
      case "Escape":
        actions.clearSelection();
        break;
      case "a":
        if (e.metaKey || e.ctrlKey) {
          e.preventDefault();
          actions.selectAllCells(table);
        }
        break;
    }
  });

  const handleCellMouseDown = useEvent(
    (e: React.MouseEvent, cell: Cell<TData, unknown>) => {
      // Right-clicks will trigger context menu, so avoid updating selected cells
      if (e.buttons === 2) {
        return;
      }

      if (isInteractiveTarget(e)) {
        return;
      }

      actions.handleCellMouseDown({
        cell,
        isShiftKey: e.shiftKey,
        isCtrlKey: e.ctrlKey,
        table,
      });
    },
  );

  const handleCellMouseUp = useEvent(() => {
    actions.setIsSelecting(false);
  });

  const handleCellMouseOver = useEvent(
    (e: React.MouseEvent, cell: Cell<TData, unknown>) => {
      if (e.buttons === 1) {
        actions.updateRangeSelection({ cell, table });
      }
    },
  );

  return {
    handleCellMouseDown,
    handleCellMouseUp,
    handleCellMouseOver,
    handleCopy,
    handleCellsKeyDown,
    updateSelection,
    clearSelection: actions.clearSelection,
  };
};

const INTERACTIVE_SELECTOR =
  'input, button, select, textarea, a, label, [role="checkbox"], [role="button"], [contenteditable="true"], marimo-ui-element';

// `<marimo-ui-element>` wraps every stateful UIElement. For content-wrapper
// UIElements (e.g. `<marimo-lazy>`), the wrapper itself is inert, so we
// treat the click as non-interactive. See https://github.com/marimo-team/marimo/issues/9189.
const CONTENT_WRAPPER_MARIMO_TAGS: ReadonlySet<string> = new Set([
  "marimo-lazy",
  "marimo-routes",
]);

/**
 * Skip cell selection when the click target is inside an interactive element
 * (e.g. a checkbox or button rendered as rich cell content).
 */
export function isInteractiveTarget(e: React.MouseEvent): boolean {
  const target = e.target;
  if (target === e.currentTarget || !(target instanceof Element)) {
    return false;
  }
  const interactiveAncestor = target.closest(INTERACTIVE_SELECTOR);
  if (!interactiveAncestor) {
    return false;
  }
  // Genuinely interactive children inside a wrapper still have their own
  // <marimo-ui-element> and are matched by closest() first.
  if (interactiveAncestor.localName === "marimo-ui-element") {
    const inner = interactiveAncestor.firstElementChild;
    if (inner && CONTENT_WRAPPER_MARIMO_TAGS.has(inner.localName)) {
      return false;
    }
  }
  return true;
}
