/* Copyright 2026 Marimo. All rights reserved. */

import type { CSSProperties } from "react";

/**
 * Left-padding (rem) for the datasource tree. Depth-based levels add
 * `step` per nesting level; fixed levels are used for engine/database/Python
 * rows and non-nested fallbacks.
 */
export const DATASOURCE_INDENT = {
  step: 1,
  engine: 0.75,
  database: 1,
  schemaHeader: 1.75,
  schemaTable: 3,
  schemaColumn: 3.25,
  tableLoading: 2.75,
  tableSchemaless: 2,
  /** In-row spacing before table row/column count metadata. */
  tableRowStats: 1.5,
  columnLocal: 1.25,
  columnPreview: 2.5,
  /** Inner padding for connection/catalog column preview fallback rows. */
  columnPreviewDetail: 1.75,
} as const;

export function schemaHeaderIndentRem(depth: number): number {
  return DATASOURCE_INDENT.schemaHeader + depth * DATASOURCE_INDENT.step;
}

export function schemaTableIndentRem(depth: number): number {
  return DATASOURCE_INDENT.schemaTable + depth * DATASOURCE_INDENT.step;
}

export function schemaColumnIndentRem(depth: number): number {
  return DATASOURCE_INDENT.schemaColumn + depth * DATASOURCE_INDENT.step;
}

export function indentStyle(rem: number): CSSProperties {
  return { paddingLeft: `${rem}rem` };
}
