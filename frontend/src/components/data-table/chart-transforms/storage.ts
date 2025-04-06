/* Copyright 2024 Marimo. All rights reserved. */

import type { CellId } from "@/core/cells/ids";
import type { ChartSchema } from "./chart-schemas";
import type { TypedString } from "@/utils/typed";
import { atomWithStorage } from "jotai/utils";
import type { z } from "zod";
import { atom } from "jotai";

export type TabName = TypedString<"TabName">;
const KEY = "marimo:charts";

export enum ChartType {
  LINE = "line",
  BAR = "bar",
  PIE = "pie",
}
export const CHART_TYPES = Object.values(ChartType);

export interface TabStorage {
  cellId: CellId;
  tabName: TabName; // unique within cell
  chartType: ChartType;
  config: z.infer<typeof ChartSchema>;
}

export const tabsStorageAtom = atomWithStorage<TabStorage[]>(KEY, []);
export const tabNumberAtom = atom(0);
