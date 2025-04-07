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
  SCATTER = "scatter",
}
export const CHART_TYPES = Object.values(ChartType);

export interface TabStorage {
  tabName: TabName; // unique within cell
  chartType: ChartType;
  config: z.infer<typeof ChartSchema>;
}

// Custom storage adapter to ensure objects are serialized as maps
const mapStorage = {
  getItem: (key: string): Map<CellId, TabStorage[]> => {
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
  setItem: (key: string, value: Map<CellId, TabStorage[]>): void => {
    localStorage.setItem(key, JSON.stringify([...value.entries()]));
  },
  removeItem: (key: string): void => {
    localStorage.removeItem(key);
  },
};

export const tabsStorageAtom = atomWithStorage<Map<CellId, TabStorage[]>>(
  KEY,
  new Map(),
  mapStorage,
);

export const tabNumberAtom = atom(0);
