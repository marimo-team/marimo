/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Custom element tag names for islands
 */
export const ISLAND_TAG_NAMES = {
  ISLAND: "marimo-island",
  CELL_OUTPUT: "marimo-cell-output",
  CELL_CODE: "marimo-cell-code",
  CODE_EDITOR: "marimo-code-editor",
} as const;

/**
 * Data attributes for islands
 */
export const ISLAND_DATA_ATTRIBUTES = {
  APP_ID: "data-app-id",
  CELL_IDX: "data-cell-idx",
  CELL_ID: "data-cell-id",
  REACTIVE: "data-reactive",
} as const;

/**
 * CSS classes for islands
 */
export const ISLAND_CSS_CLASSES = {
  NAMESPACE: "marimo",
} as const;
