/* Copyright 2024 Marimo. All rights reserved. */

import type { DataType } from "@/core/kernel/messages";
import { Objects } from "@/utils/objects";

export interface ColumnHeaderSummary {
  column: string | number;
  min?: number | string | undefined | null;
  max?: number | string | undefined | null;
  unique?: number | unknown[] | undefined | null;
  nulls?: number | null;
  true?: number | null;
  false?: number | null;
}

export type FieldTypesWithExternalType = Array<
  [columnName: string, [dataType: DataType, externalType: string]]
>;
export type FieldTypes = Record<string, DataType>;

export function toFieldTypes(
  fieldTypes: FieldTypesWithExternalType,
): FieldTypes {
  return Objects.collect(
    fieldTypes,
    ([columnName]) => columnName,
    ([, [type]]) => type,
  );
}

export const SELECT_COLUMN_ID = "__select__";
