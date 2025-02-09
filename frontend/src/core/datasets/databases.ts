/* Copyright 2024 Marimo. All rights reserved. */
import { createReducerAndAtoms } from "@/utils/createReducer";
import type { Database, SQLTablesPreview } from "../kernel/messages";

export interface DatabaseState {
  databasesMap: ReadonlyMap<string, Database>;
  expandedSchemas: ReadonlySet<string>;
}

function initialState(): DatabaseState {
  return {
    databasesMap: new Map(),
    expandedSchemas: new Set(),
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

  addSQLTablesPreview: (
    state: DatabaseState,
    preview: SQLTablesPreview,
  ): DatabaseState => {
    console.log("preview", preview);
    const database = state.databasesMap.get(preview.database_name);
    if (!database) {
      return state;
    }
    console.log("preview", preview);

    return state;
  },

  addSQLTableInfoPreview: (
    state: DatabaseState,
    preview: SQLTablesPreview,
  ): DatabaseState => {
    const database = state.databasesMap.get(preview.database_name);
    if (!database) {
      return state;
    }
    console.log("preview", preview);

    return state;
  },
});

export { reducer, createActions, databasesAtom, useDatabaseActions };
