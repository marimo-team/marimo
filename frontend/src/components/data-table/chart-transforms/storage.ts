/* Copyright 2024 Marimo. All rights reserved. */

import type { CellId } from "@/core/cells/ids";
import type { LineChartSchema } from "./chart-schemas";
import type { TypedString } from "@/utils/typed";
import { atomWithStorage } from "jotai/utils";
import type { z } from "zod";

export type TabName = TypedString<"TabName">;
const KEY = "marimo:charts";

export type ChartType = "line" | "bar" | "pie";

export interface TabStorage {
  cellId: CellId;
  tabName: TabName; // unique within cell
  chartType: ChartType;
  config: z.infer<typeof LineChartSchema>;
}

export const tabsStorageAtom = atomWithStorage<TabStorage[]>(KEY, []);
