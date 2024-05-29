/* Copyright 2024 Marimo. All rights reserved. */
import type { JsonString } from "@/utils/json/base64";
import type { DataTable } from "../network/types";

/**
 * A qualified column name, e.g. `table:column`.
 */
export type QualifiedColumn = `${string}:${string}`;

/**
 * A summary of a column's statistics.
 */
export interface ColumnPreviewSummary {
  error?: string;
  total?: number;
  nulls?: number;
  unique?: number;
  min?: number;
  max?: number;
  mean?: number;
  median?: number;
  std?: number;
  p5?: number;
  p25?: number;
  p75?: number;
  p95?: number;
}

export type ColumnPreviewMap = ReadonlyMap<
  QualifiedColumn,
  {
    chart_spec?: JsonString;
    chart_code?: string;
    error?: string;
    summary?: ColumnPreviewSummary;
  }
>;

/**
 * The datasets state.
 */
export interface DatasetsState {
  tables: DataTable[];
  expandedTables: ReadonlySet<string>;
  expandedColumns: ReadonlySet<QualifiedColumn>;
  columnsPreviews: ColumnPreviewMap;
}
