/* Copyright 2023 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-redeclare */

import { invariant } from "@/utils/invariant";
import { TypedString } from "./typed";

/**
 * A typed CellId
 */
export type CellId = TypedString<"CellId">;
let counter = 0;
export const CellId = {
  /**
   * Create a new CellId
   */
  create(): CellId {
    const next = counter++;
    return next.toString() as CellId;
  },

  /**
   * Reset id provider.
   */
  reset() {
    counter = 0;
  },
};

/**
 * The id of an HTML element that represents a cell
 */
export type HTMLCellId = `cell-${CellId}`;
export const HTMLCellId = {
  /**
   * Create a new HTMLCellId
   */
  create(cellId: CellId): HTMLCellId {
    invariant(cellId != null, "cellId is required");

    return `cell-${cellId}` as HTMLCellId;
  },
  parse(htmlCellId: HTMLCellId): CellId {
    return htmlCellId.slice(5) as CellId;
  },
  /**
   * Get the cell container ancestor of `element`, if any.
   */
  findElement(element: Element): (Element & { id: HTMLCellId }) | null {
    return element.closest('div[id^="cell-"]');
  },
};
