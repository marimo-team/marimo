/* Copyright 2024 Marimo. All rights reserved. */
import { createReducerAndAtoms } from "@/utils/createReducer";
import type { Database, DataTable } from "../kernel/messages";

export interface DatabaseState {
  databasesMap: ReadonlyMap<string, Database>;
  tablePreviews: ReadonlyMap<string, DataTable>;
}

function initialState(): DatabaseState {
  return {
    databasesMap: new Map(),
    tablePreviews: new Map(),
  };
  //   return {
  //     databasesMap: new Map().set(DEFAULT_ENGINE, {
  //       name: "memory",
  //       engine: DEFAULT_ENGINE,
  //       source: "duckdb",
  //       schemas: {
  //         main: { name: "main", tables: {} },
  //       },
  //     }),
  //   };
}

const {
  reducer,
  createActions,
  valueAtom: databasesAtom,
  useActions: useDatabaseActions,
} = createReducerAndAtoms(initialState, {
  addDatabase: (
    state: DatabaseState,
    opts: { databases: Database[] },
  ): DatabaseState => {
    if (opts.databases.length === 0) {
      return state;
    }
    const databases = opts.databases;
    const newDatabaseMap = new Map(state.databasesMap);
    for (const db of databases) {
      newDatabaseMap.set(db.name, db);
    }

    return {
      ...state,
      databasesMap: newDatabaseMap,
    };
  },

  addTablePreview: (state, opts: { table: DataTable }): DatabaseState => {
    const newTablePreviews = new Map(state.tablePreviews);
    newTablePreviews.set(opts.table.name, opts.table);
    return {
      ...state,
      tablePreviews: newTablePreviews,
    };
  },
});

export { reducer, createActions, databasesAtom, useDatabaseActions };
