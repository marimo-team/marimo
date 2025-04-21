/* Copyright 2024 Marimo. All rights reserved. */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { getDefaultStore } from "jotai";
import { tabsStorageAtom, KEY } from "../storage";
import { ChartSchema } from "../chart-schemas";
import type { CellId } from "@/core/cells/ids";
import type { TabName } from "../storage";
import { ChartType } from "../constants";

// Mock localStorage
const mockLocalStorage = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
  length: 0,
  key: vi.fn(),
};

// Mock window.localStorage
Object.defineProperty(window, "localStorage", {
  value: mockLocalStorage,
  writable: true,
});

describe("Chart Transforms Storage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset the store before each test
    const store = getDefaultStore();
    store.set(tabsStorageAtom, new Map());
  });

  describe("tabsStorageAtom", () => {
    it("should initialize with an empty Map", () => {
      const store = getDefaultStore();
      const value = store.get(tabsStorageAtom);
      expect(value).toBeInstanceOf(Map);
      expect(value.size).toBe(0);
    });

    it("should store and retrieve tab data", () => {
      const store = getDefaultStore();
      const cellId = "cell-1" as CellId;
      const tabData = {
        tabName: "Tab 1" as TabName,
        chartType: ChartType.LINE,
        config: ChartSchema.parse({
          general: {
            xColumn: {},
            yColumn: {},
          },
        }),
      };

      // Set the atom value
      const newMap = new Map();
      newMap.set(cellId, [tabData]);
      store.set(tabsStorageAtom, newMap);

      // Verify the value was set
      const retrievedValue = store.get(tabsStorageAtom);
      expect(retrievedValue.get(cellId)).toEqual([tabData]);
    });

    it("should handle multiple tabs for the same cell", () => {
      const store = getDefaultStore();
      const cellId = "cell-1" as CellId;
      const tabData1 = {
        tabName: "Tab 1" as TabName,
        chartType: ChartType.LINE,
        config: ChartSchema.parse({
          general: {
            xColumn: {},
            yColumn: {},
          },
        }),
      };
      const tabData2 = {
        tabName: "Tab 2" as TabName,
        chartType: ChartType.BAR,
        config: ChartSchema.parse({
          general: {
            xColumn: {},
            yColumn: {},
          },
        }),
      };

      // Set the atom value
      const newMap = new Map();
      newMap.set(cellId, [tabData1, tabData2]);
      store.set(tabsStorageAtom, newMap);

      // Verify the value was set
      const retrievedValue = store.get(tabsStorageAtom);
      expect(retrievedValue.get(cellId)).toEqual([tabData1, tabData2]);
    });
  });

  describe("LocalStorage integration", () => {
    it("should call localStorage.setItem when setting data", () => {
      // Reset the mock to ensure clean state
      mockLocalStorage.setItem.mockReset();

      const store = getDefaultStore();
      const newMap = new Map();
      store.set(tabsStorageAtom, newMap);

      expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
        KEY,
        JSON.stringify([]),
      );
    });
  });
});
