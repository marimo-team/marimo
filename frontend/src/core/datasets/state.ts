/* Copyright 2024 Marimo. All rights reserved. */

import { atom, useAtomValue } from "jotai";
import { createReducerAndAtoms } from "@/utils/createReducer";
import type {
  DataColumnPreview,
  OperationMessageData,
} from "../kernel/messages";
import { previewDatasetColumn } from "../network/requests";
import type { VariableName } from "../variables/types";
import type { DatasetsState } from "./types";

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
  addDatasets: (state, datasets: OperationMessageData<"datasets">) => {
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
            sourceType: table.source_type,
          });
        }
      }
    }

    // Prev tables
    let prevTables = state.tables;
    if (datasets.clear_channel) {
      prevTables = prevTables.filter((table) => {
        return table.source !== datasets.clear_channel;
      });
    }

    // Put new tables at the top
    const newTables = [...datasets.tables, ...prevTables];

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
      // If there's no variable name, it's not a variable and we should keep it
      if (!table.variable_name) {
        return true;
      }
      return names.has(table.variable_name as VariableName);
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

export const datasetTablesAtom = atom((get) => get(datasetsAtom).tables);

export const expandedColumnsAtom = atom(new Set<string>());
export const closeAllColumnsAtom = atom(false);

/**
 * React hook to get the datasets actions.
 */
export function useDatasetsActions() {
  return useActions();
}

export { datasetsAtom };

export const exportedForTesting = {
  reducer,
  createActions,
  initialState,
};
