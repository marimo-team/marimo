/* Copyright 2024 Marimo. All rights reserved. */
export interface ColumnHeaderSummary {
  column: string | number;
  min?: number | string | undefined | null;
  max?: number | string | undefined | null;
  unique?: number | null;
  nulls?: number | null;
}
