/* Copyright 2024 Marimo. All rights reserved. */

import { invariant } from "@/utils/invariant";
import type { TypedString } from "../../utils/typed";

const lowercase = "abcdefghijklmnopqrstuvwxyz";
const uppercase = lowercase.toUpperCase();
const alphabet = lowercase + uppercase;
const seen = new Set<CellId>();

/**
 * A typed CellId
 */
export type CellId = TypedString<"CellId">;
export const CellId = {
  /**
   * Create a new CellId, a random 4 letter string.
   */
  create(): CellId {
    let attempts = 0;
    let cellId: CellId;

    do {
      let id = "";
      for (let i = 0; i < 4; i++) {
        id += alphabet[Math.floor(Math.random() * alphabet.length)];
      }
      cellId = id as CellId;
      attempts++;
    } while (seen.has(cellId) && attempts < 100);

    if (attempts >= 100) {
      throw new Error("Failed to generate unique CellId after 100 attempts");
    }

    seen.add(cellId);
    return cellId;
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

  /**
   * Find the cell element through shadow DOMs.
   */
  findElementThroughShadowDOMs(
    element: Element,
  ): (Element & { id: HTMLCellId }) | null {
    let currentElement: Element | null = element;

    while (currentElement) {
      const cellElement = HTMLCellId.findElement(currentElement);
      if (cellElement) {
        return cellElement;
      }

      const root = currentElement.getRootNode();
      currentElement =
        root instanceof ShadowRoot ? root.host : currentElement.parentElement;

      if (currentElement === root) {
        break;
      }
    }

    return null;
  },
};

/**
 * Find the cellId of an element
 */
export function findCellId(element: HTMLElement): CellId | null {
  let cellId: CellId | null = null;
  const cellContainer = HTMLCellId.findElement(element);
  if (cellContainer) {
    cellId = HTMLCellId.parse(cellContainer.id);
  }
  return cellId;
}

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

export type CellOutputId = `output-${CellId}`;
export const CellOutputId = {
  create(cellId: CellId): CellOutputId {
    return `output-${cellId}`;
  },
};
