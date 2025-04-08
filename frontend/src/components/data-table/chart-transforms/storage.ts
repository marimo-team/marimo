/* Copyright 2024 Marimo. All rights reserved. */

import type { CellId } from "@/core/cells/ids";
import type { TypedString } from "@/utils/typed";
import { atomWithStorage } from "jotai/utils";
import { z } from "zod";
import { atom } from "jotai";
import { ZodLocalStorage } from "@/utils/localStorage";
import { ChartSchema } from "./chart-schemas";

export type TabName = TypedString<"TabName">;
const KEY = "marimo:charts";

export enum ChartType {
  LINE = "line",
  BAR = "bar",
  PIE = "pie",
  SCATTER = "scatter",
}
export const CHART_TYPES = Object.values(ChartType);

interface TabStorage {
  tabName: TabName; // unique within cell
  chartType: ChartType;
  config: z.infer<typeof ChartSchema>;
}
type TabStorageMap = Map<CellId, TabStorage[]>;

const tabStorageSchema = z.map(
  z.string().transform((val) => val as CellId),
  z.array(
    z.object({
      tabName: z.string().transform((val) => val as TabName),
      chartType: z
        .enum(CHART_TYPES as [string, ...string[]])
        .transform((val) => val as ChartType),
      config: ChartSchema,
    }),
  ),
);

const storage = new ZodLocalStorage<TabStorageMap>(
  KEY,
  tabStorageSchema,
  () => new Map(),
);
const storageMechanism = {
  getItem: (): TabStorageMap => storage.get(),
  setItem: (_key: string, value: TabStorageMap): void => storage.set(value),
  removeItem: (): void => storage.remove(),
};

export const tabsStorageAtom = atomWithStorage<TabStorageMap>(
  KEY,
  new Map(),
  storageMechanism,
);
export const tabNumberAtom = atom(0);
