/* Copyright 2024 Marimo. All rights reserved. */
import {
  type TableFeature,
  type RowData,
  type Table,
  type Column,
  type Updater,
  makeStateUpdater,
} from "@tanstack/react-table";
import type { CellHeatmapTableState, CellHeatmapOptions } from "./types";

export const CellHeatmapFeature: TableFeature = {
  getInitialState: (state): CellHeatmapTableState => {
    return {
      columnHeatmap: {},
      cachedMaxValue: null,
      cachedMinValue: null,
      ...state,
    };
  },

  getDefaultOptions: <TData extends RowData>(
    table: Table<TData>,
  ): CellHeatmapOptions => {
    return {
      enableCellHeatmap: true,
      onColumnHeatmapChange: makeStateUpdater("columnHeatmap", table),
    };
  },

  createTable: <TData extends RowData>(table: Table<TData>) => {
    table.getGlobalHeatmap = () => {
      return Object.values(table.getState().columnHeatmap).some(Boolean);
    };

    table.toggleGlobalHeatmap = () => {
      const allColumns = table.getAllColumns();
      const { columnHeatmap } = table.getState();
      const hasAnyEnabled = Object.values(columnHeatmap).some(Boolean);

      if (hasAnyEnabled) {
        // Disable all columns
        table.options.onColumnHeatmapChange?.(
          Object.fromEntries(allColumns.map((column) => [column.id, false])),
        );
      } else {
        // Enable all columns
        table.options.onColumnHeatmapChange?.(
          Object.fromEntries(allColumns.map((column) => [column.id, true])),
        );
      }

      table.setState((old) => ({
        ...old,
        cachedMinValue: null,
        cachedMaxValue: null,
      }));
    };
  },

  createColumn: <TData extends RowData>(
    column: Column<TData>,
    table: Table<TData>,
  ) => {
    // Clear min/max cache when a column is added or removed
    table.setState((old) => ({
      ...old,
      cachedMinValue: null,
      cachedMaxValue: null,
    }));

    column.getCellHeatmapColor = (cellValue: unknown) => {
      const state = table.getState();
      const isColumnHeatmapEnabled = Boolean(state.columnHeatmap[column.id]);
      if (!isColumnHeatmapEnabled || typeof cellValue !== "number") {
        return "";
      }

      // Get all numeric values from enabled columns
      let minValue = state.cachedMinValue;
      let maxValue = state.cachedMaxValue;

      if (minValue == null || maxValue == null) {
        const { min, max } = getMaxMinValue(table);
        minValue = min;
        maxValue = max;
        table.setState((old) => ({
          ...old,
          cachedMinValue: minValue,
          cachedMaxValue: maxValue,
        }));
      }

      const isDarkMode =
        typeof window !== "undefined" &&
        "matchMedia" in window &&
        typeof window.matchMedia === "function" &&
        window.matchMedia("(prefers-color-scheme: dark)").matches;

      const colorStops = isDarkMode
        ? [
            { hue: 210, saturation: 100, lightness: 30 }, // Darker Blue
            { hue: 199, saturation: 95, lightness: 33 }, // Darker Cyan
            { hue: 172, saturation: 66, lightness: 30 }, // Darker Teal
            { hue: 158, saturation: 64, lightness: 32 }, // Darker Green
            { hue: 142, saturation: 71, lightness: 25 }, // Darker Lime
            { hue: 47, saturation: 96, lightness: 33 }, // Darker Yellow
            { hue: 21, saturation: 90, lightness: 28 }, // Darker Orange
            { hue: 0, saturation: 84, lightness: 40 }, // Darker Red
          ]
        : [
            { hue: 210, saturation: 100, lightness: 50 }, // Blue-500
            { hue: 199, saturation: 95, lightness: 53 }, // Cyan-500
            { hue: 172, saturation: 66, lightness: 50 }, // Teal-500
            { hue: 158, saturation: 64, lightness: 52 }, // Green-500
            { hue: 142, saturation: 71, lightness: 45 }, // Lime-600
            { hue: 47, saturation: 96, lightness: 53 }, // Yellow-400
            { hue: 21, saturation: 90, lightness: 48 }, // Orange-500
            { hue: 0, saturation: 84, lightness: 60 }, // Red-500
          ];

      // Normalize the cellValue
      const normalized = (cellValue - minValue) / (maxValue - minValue);

      const index = Math.min(
        Math.floor(normalized * (colorStops.length - 1)),
        colorStops.length - 2,
      );
      const t = normalized * (colorStops.length - 1) - index;

      const c1 = colorStops[index];
      const c2 = colorStops[index + 1];

      if (!c1 || !c2) {
        return "";
      }

      const hue = Math.round(c1.hue + t * (c2.hue - c1.hue));
      const saturation = Math.round(
        c1.saturation + t * (c2.saturation - c1.saturation),
      );
      const lightness = Math.round(
        c1.lightness + t * (c2.lightness - c1.lightness),
      );

      return `hsla(${hue}, ${saturation}%, ${lightness}%, 0.6)`;
    };

    column.toggleColumnHeatmap = (value?: boolean) => {
      const safeUpdater: Updater<CellHeatmapTableState["columnHeatmap"]> = (
        old,
      ) => {
        const prevValue = old[column.id];
        if (value !== undefined) {
          return {
            ...old,
            [column.id]: value,
          };
        }

        return {
          ...old,
          [column.id]: !prevValue,
        };
      };

      table.options.onColumnHeatmapChange?.(safeUpdater);
      table.setState((old) => ({
        ...old,
        cachedMinValue: null,
        cachedMaxValue: null,
      }));
    };

    column.getIsColumnHeatmapEnabled = () => {
      return table.getState().columnHeatmap[column.id] || false;
    };
  },
};

function getMaxMinValue<TData extends RowData>(table: Table<TData>) {
  const { columnHeatmap } = table.getState();
  const enabledColumnsSet = new Set(
    Object.keys(columnHeatmap).filter((key) => columnHeatmap[key]),
  );
  const values: number[] = [];
  for (const row of table.getRowModel().rows) {
    for (const column of table.getAllColumns()) {
      if (enabledColumnsSet.has(column.id)) {
        const cellValue = row.getValue(column.id);
        if (typeof cellValue === "number" && !Number.isNaN(cellValue)) {
          values.push(cellValue);
        }
      }
    }
  }

  return {
    min: Math.min(...values),
    max: Math.max(...values),
  };
}
