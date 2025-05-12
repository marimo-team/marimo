/* Copyright 2024 Marimo. All rights reserved. */

import type { CellId } from "@/core/cells/ids";
import type { TypedString } from "@/utils/typed";
import { atomWithStorage } from "jotai/utils";
import { z } from "zod";
import { atom } from "jotai";
import { ChartSchema } from "./chart-schemas";
import { Logger } from "@/utils/Logger";
import type { ChartType } from "./types";
import { NotebookScopedLocalStorage } from "@/utils/localStorage";

export type TabName = TypedString<"TabName">;
export const KEY = "marimo:charts:v2";

interface TabStorage {
  tabName: TabName; // unique within cell
  chartType: ChartType;
  config: z.infer<typeof ChartSchema>;
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
export const tabNumberAtom = atom(0);
