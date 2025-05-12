/* Copyright 2024 Marimo. All rights reserved. */

import type { CellId } from "@/core/cells/ids";
import type { TypedString } from "@/utils/typed";
import { atomWithStorage } from "jotai/utils";
import { z } from "zod";
import { ChartSchema, type ChartSchemaType } from "./schemas";
import { Logger } from "@/utils/Logger";
import type { ChartType } from "./types";
import { NotebookScopedLocalStorage } from "@/utils/localStorage";
import { capitalize } from "lodash-es";

export type TabName = TypedString<"TabName">;
export const KEY = "marimo:charts:v2";

interface TabStorage {
  tabName: TabName; // unique within cell
  chartType: ChartType;
  config: ChartSchemaType;
}

type TabStorageMap = Map<CellId, TabStorage[]>;

const TabStorageSchema = z.object({
  tabName: z.string().transform((name) => name as TabName),
  chartType: z.string().transform((type) => type as ChartType),
  config: ChartSchema,
});
const TabStorageEntriesSchema = z.array(
  z.tuple([
    z.string().transform((name) => name as CellId),
    z.array(TabStorageSchema),
  ]),
);

const storage = new NotebookScopedLocalStorage(
  KEY,
  TabStorageEntriesSchema,
  () => [],
);

// Custom storage adapter to ensure objects are serialized as maps
const mapStorage = {
  getItem: (key: string): TabStorageMap => {
    try {
      const value = storage.get(key);
      return new Map(value);
    } catch (error) {
      Logger.warn("Error getting chart storage", error);
      return new Map();
    }
  },
  setItem: (key: string, value: TabStorageMap): void => {
    storage.set(key, [...value.entries()]);
  },
  removeItem: (key: string): void => {
    storage.remove(key);
  },
};

export const tabsStorageAtom = atomWithStorage<TabStorageMap>(
  KEY,
  new Map(),
  mapStorage,
);

/**
 * Convenience function to get the tab name for a given tab number and chart type
 */
export function getChartTabName(tabNum: number, chartType: ChartType) {
  const capitalizedChartType = capitalize(chartType);
  if (tabNum === 0) {
    return `${capitalizedChartType} Chart` as TabName;
  }
  return `${capitalizedChartType} Chart ${tabNum + 1}` as TabName;
}

const initialStorageValue = mapStorage.getItem(KEY);
/**
 * Returns true if the cell has a chart
 */
export function hasChart(cellId: CellId) {
  const tabs = initialStorageValue.get(cellId);
  if (!tabs) {
    return false;
  }
  return tabs.length > 0;
}
