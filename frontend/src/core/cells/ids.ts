/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-redeclare */

import { invariant } from "@/utils/invariant";
import type { TypedString } from "../../utils/typed";

const lowercase = "abcdefghijklmnopqrstuvwxyz";
const uppercase = lowercase.toUpperCase();
const alphabet = lowercase + uppercase;

/**
 * A typed CellId
 */
export type CellId = TypedString<"CellId">;
export const CellId = {
  /**
   * Create a new CellId, a random 4 letter string.
   */
  create(): CellId {
    let id = "";
    for (let i = 0; i < 4; i++) {
      id += alphabet[Math.floor(Math.random() * alphabet.length)];
    }
    return id as CellId;
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
export const useFindCellId = (element: HTMLElement) => {
  let cellId: CellId | null = null;
  const cellContainer = HTMLCellId.findElement(element);
  if (cellContainer) {
    cellId = HTMLCellId.parse(cellContainer.id);
  }
  return cellId;
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

export type CellOutputId = `output-${CellId}`;
export const CellOutputId = {
  create(cellId: CellId): CellOutputId {
    return `output-${cellId}`;
  },
};
