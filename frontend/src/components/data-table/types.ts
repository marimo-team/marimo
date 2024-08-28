/* Copyright 2024 Marimo. All rights reserved. */

import type { DataType } from "@/core/kernel/messages";

export interface ColumnHeaderSummary {
  column: string | number;
  min?: number | string | undefined | null;
  max?: number | string | undefined | null;
  unique?: number | null;
  nulls?: number | null;
  true?: number | null;
  false?: number | null;
}

export type FieldTypesWithExternalType = Record<
  string,
  [DataType, externalType: string]
>;
export type FieldTypes = Record<string, DataType>;

export const SELECT_COLUMN_ID = "__select__";
