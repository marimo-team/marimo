/* Copyright 2024 Marimo. All rights reserved. */

export const DEFAULT_CELL_NAME = "__";

// Generated with `python scripts/print_banned_cell_names.py`
const DISALLOWED_NAMES = new Set([
  "__*",
  "marimo",
  "app",
  "False",
  "None",
  "True",
  "__peg_parser__",
  "and",
  "as",
  "assert",
  "async",
  "await",
  "break",
  "class",
  "continue",
  "def",
  "del",
  "elif",
  "else",
  "except",
  "finally",
  "for",
  "from",
  "global",
  "if",
  "import",
  "in",
  "is",
  "lambda",
  "nonlocal",
  "not",
  "or",
  "pass",
  "raise",
  "return",
  "try",
  "while",
  "with",
  "yield",
  "None",
]);

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

  const isValid = (name: string) => {
    return !set.has(name) && !DISALLOWED_NAMES.has(name);
  };

  if (isValid(name)) {
    return name;
  }

  let count = 1;
  while (!isValid(result)) {
    result = `${name}_${count}`;
    count++;
  }

  return result;
}

/**
 * Print the cell name if differs from DEFAULT_CELL_NAME
 */
export function displayCellName(name: string, cellIndex: number): string {
  if (name !== DEFAULT_CELL_NAME) {
    return name;
  }
  return `cell-${cellIndex}`;
}
