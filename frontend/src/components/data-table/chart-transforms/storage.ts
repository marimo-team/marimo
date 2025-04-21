/* Copyright 2024 Marimo. All rights reserved. */

import type { CellId } from "@/core/cells/ids";
import type { TypedString } from "@/utils/typed";
import { atomWithStorage } from "jotai/utils";
import type { z } from "zod";
import { atom } from "jotai";
import type { ChartSchema } from "./chart-schemas";
import { Logger } from "@/utils/Logger";
import type { ChartType } from "./constants";
export type TabName = TypedString<"TabName">;
export const KEY = "marimo:charts:v1";

interface TabStorage {
  tabName: TabName; // unique within cell
  chartType: ChartType;
  config: z.infer<typeof ChartSchema>;
}
type TabStorageMap = Map<CellId, TabStorage[]>;

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
    } catch (error) {
      Logger.warn("Error getting chart storage", error);
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
