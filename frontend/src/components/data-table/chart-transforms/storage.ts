/* Copyright 2024 Marimo. All rights reserved. */

import type { CellId } from "@/core/cells/ids";
import type { TypedString } from "@/utils/typed";
import { atomWithStorage } from "jotai/utils";
import type { z } from "zod";
import { atom } from "jotai";
import type { ChartSchema } from "./chart-schemas";

export type TabName = TypedString<"TabName">;
export const KEY = "marimo:charts";

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

// const tabStorageSchema = z.map(
//   z.string().transform((val) => val as CellId),
//   z.array(
//     z.object({
//       tabName: z.string().transform((val) => val as TabName),
//       chartType: z
//         .enum(CHART_TYPES as [string, ...string[]])
//         .transform((val) => val as ChartType),
//       config: ChartSchema,
//     }),
//   ),
// );

// const storage = new ZodLocalStorage<TabStorageMap>(
//   KEY,
//   tabStorageSchema,
//   () => new Map(),
// );
// const storageMechanism = {
//   getItem: (): TabStorageMap => storage.get(),
//   setItem: (_key: string, value: TabStorageMap): void => storage.set(value),
//   removeItem: (): void => storage.remove(),
// };

// Custom storage adapter to ensure objects are serialized as maps
const mapStorage = {
  getItem: (key: string): TabStorageMap => {
    try {
      const value = localStorage.getItem(key);
      if (!value) {
        return new Map();
      }
      const parsed = JSON.parse(value);
      return new Map(parsed as Array<[CellId, TabStorage[]]>);
    } catch {
      return new Map();
    }
  },
  setItem: (key: string, value: TabStorageMap): void => {
    localStorage.setItem(key, JSON.stringify([...value.entries()]));
  },
  removeItem: (key: string): void => {
    localStorage.removeItem(key);
  },
};

export const tabsStorageAtom = atomWithStorage<TabStorageMap>(
  KEY,
  new Map(),
  mapStorage,
);
export const tabNumberAtom = atom(0);
