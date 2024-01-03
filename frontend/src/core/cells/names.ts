/* Copyright 2023 Marimo. All rights reserved. */

import { CellId, HTMLCellId } from "./ids";

export const DEFAULT_CELL_NAME = "__";

/**
 * Make's name pythonic - removes spaces, special characters and makes lowercase
 */
export function normalizeName(name: string) {
  name = name.trim();
  if (!name) {
    return DEFAULT_CELL_NAME;
  }
  // Cannot start with a number
  if (/^\d/.test(name)) {
    name = `_${name}`;
  }
  return name.replaceAll(/\W/g, "_").toLowerCase();
}

/**
 * Get a non-conflicting name
 */
export function getValidName(name: string, existingNames: string[]): string {
  const set = new Set(existingNames);
  let result = name;

  if (!set.has(name)) {
    return name;
  }

  let count = 1;
  while (set.has(result)) {
    result = `${name}_${count}`;
    count++;
  }

  return result;
}

/**
 * Print the cell name if differs from DEFAULT_CELL_NAME
 */
export function displayCellName(name: string, fallbackCellId: CellId): string {
  if (name !== DEFAULT_CELL_NAME) {
    return name;
  }
  return HTMLCellId.create(fallbackCellId);
}
