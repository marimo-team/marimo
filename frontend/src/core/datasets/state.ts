/* Copyright 2024 Marimo. All rights reserved. */

import { createReducerAndAtoms } from "@/utils/createReducer";
import type { DatasetsState } from "./types";
import { useAtomValue } from "jotai";
import { VariableName } from "../variables/types";
import { DataColumnPreview } from "../kernel/messages";
import { previewDatasetColumn } from "../network/requests";

function initialState(): DatasetsState {
  return {
    tables: [],
    expandedTables: new Set(),
    expandedColumns: new Set(),
    columnsPreviews: new Map(),
  };
}

const {
  reducer,
  createActions,
  valueAtom: datasetsAtom,
  useActions,
} = createReducerAndAtoms(initialState, {
  addDatasets: (state, datasets: Pick<DatasetsState, "tables">) => {
    // Quietly in the background make requests to get the previews for
    // opened columns, in the new tables
    for (const table of datasets.tables) {
      for (const column of table.columns) {
        const tableColumn = `${table.name}:${column.name}` as const;
        if (state.expandedColumns.has(tableColumn)) {
          // Fire and forget
          void previewDatasetColumn({
            tableName: table.name,
            columnName: column.name,
            source: table.source,
          });
        }
      }
    }

    // Put new tables at the top
    const newTables = [...datasets.tables, ...state.tables];

    // Dedupe by name and source
    const seen = new Set();
    const dedupedTables = newTables.filter((table) => {
      const key = `${table.name}:${table.source}`;
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
    const sortedTables = dedupedTables.sort((a, b) => {
      return a.name.localeCompare(b.name);
    });
    return {
      ...state,
      tables: sortedTables,
    };
  },
  filterDatasetsFromVariables: (state, variableNames: VariableName[]) => {
    const names = new Set(variableNames);
    // Filter out tables that come from variables that are not in the list
    const tables = state.tables.filter((table) => {
      return table.variable_name && names.has(table.variable_name);
    });
    return { ...state, tables };
  },
  toggleTable: (state, tableName: string) => {
    const expandedTables = new Set(state.expandedTables);
    if (expandedTables.has(tableName)) {
      expandedTables.delete(tableName);
    } else {
      expandedTables.add(tableName);
    }
    return { ...state, expandedTables };
  },
  toggleColumn: (state, opts: { table: string; column: string }) => {
    const tableColumn = `${opts.table}:${opts.column}` as const;
    const expandedColumns = new Set(state.expandedColumns);
    if (expandedColumns.has(tableColumn)) {
      expandedColumns.delete(tableColumn);
    } else {
      expandedColumns.add(tableColumn);
    }
    return { ...state, expandedColumns };
  },
  closeAllColumns: (state) => {
    return { ...state, expandedColumns: new Set() };
  },
  addColumnPreview: (state, preview: DataColumnPreview) => {
    const tableColumn = `${preview.table_name}:${preview.column_name}` as const;
    const columnsPreviews = new Map(state.columnsPreviews);
    columnsPreviews.set(tableColumn, preview);
    return { ...state, columnsPreviews };
  },
});

/**
 * React hook to get the datasets state.
 */
export const useDatasets = () => useAtomValue(datasetsAtom);

/**
 * React hook to get the datasets actions.
 */
export function useDatasetsActions() {
  return useActions();
}

export const exportedForTesting = {
  reducer,
  createActions,
  initialState,
};
