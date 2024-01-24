/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-redeclare */

import { invariant } from "@/utils/invariant";
import { TypedString } from "../../utils/typed";

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

    return `cell-${cellId}`;
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

/**
 * A typed UIElementId
 */
export type UIElementId = `${CellId}-${string}`;
export const UIElementId = {
  parse(element: Element): UIElementId | null {
    return element.getAttribute("object-id") as UIElementId | null;
  },
  parseOrThrow(element: Element): UIElementId {
    const id = UIElementId.parse(element);
    invariant(id, "<marimo-ui-element/> missing object-id attribute");
    return id;
  },
};
