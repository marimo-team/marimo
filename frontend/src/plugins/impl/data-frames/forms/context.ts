/* Copyright 2023 Marimo. All rights reserved. */
import { createContext } from "react";
import { ColumnDataTypes } from "../types";

export const ColumnInfoContext = createContext<ColumnDataTypes>({});

export const ColumnNameContext = createContext<string>("");
export const ColumnFetchValuesContext = createContext<
  (req: { column: string }) => Promise<{
    values: unknown[];
    too_many_values: boolean;
  }>
>(() => Promise.resolve({ values: [], too_many_values: false }));
