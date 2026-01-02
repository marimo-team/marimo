/* Copyright 2026 Marimo. All rights reserved. */
import { createContext } from "react";
import type { ColumnDataTypes } from "../types";

export const ColumnInfoContext = createContext<ColumnDataTypes>(new Map());

export const ColumnNameContext = createContext<string>("");
export const ColumnFetchValuesContext = createContext<
  (req: { column: string }) => Promise<{
    values: unknown[];
    too_many_values: boolean;
  }>
>(() => Promise.resolve({ values: [], too_many_values: false }));
