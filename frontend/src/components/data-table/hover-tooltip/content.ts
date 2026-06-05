/* Copyright 2026 Marimo. All rights reserved. */
import type { Cell, RowData } from "@tanstack/react-table";
import type { ReactNode } from "react";
import { stringifyUnknownValue } from "../utils";

export function applyHoverTemplate<TData extends RowData>(
  template: string,
  cells: Cell<TData, unknown>[],
): string {
  const variableRegex = /{{(\w+)}}/g;
  const idToValue = new Map<string, string>();
  for (const c of cells) {
    const s = stringifyUnknownValue({
      value: c.getValue(),
      nullAsEmptyString: true,
    });
    idToValue.set(c.column.id, s);
  }
  return template.replaceAll(variableRegex, (_substr, varName: string) => {
    const val = idToValue.get(varName);
    return val === undefined ? `{{${varName}}}` : val;
  });
}

/**
 * Resolve the tooltip content for a hovered cell.
 *
 * Cell-level (callable `hover_template`) takes precedence; otherwise the
 * row-level string template is rendered against the row's visible cells.
 * Returns `undefined` when there is nothing to show.
 */
export function computeCellTooltipContent<TData extends RowData>(
  cell: Cell<TData, unknown>,
  hoverTemplate: string | null,
): ReactNode {
  const cellTitle = cell.getHoverTitle?.();
  if (cellTitle != null && cellTitle !== "") {
    return cellTitle;
  }
  if (hoverTemplate) {
    return applyHoverTemplate(hoverTemplate, cell.row.getVisibleCells());
  }
  return undefined;
}
