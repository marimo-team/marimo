/* Copyright 2024 Marimo. All rights reserved. */
import { createReducerAndAtoms } from "@/utils/createReducer";
import type { Database, SQLTablePreview } from "../kernel/messages";
import { atom } from "jotai";

export interface DatabaseState {
  databasesMap: ReadonlyMap<string, Database>;
  tablePreviews: ReadonlyMap<string, SQLTablePreview>;
}

function initialState(): DatabaseState {
  return {
    databasesMap: new Map(),
    tablePreviews: new Map(),
  };
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

  addTablePreview: (state, preview: SQLTablePreview): DatabaseState => {
    const newTablePreviews = new Map(state.tablePreviews);
    if (preview.table?.name) {
      newTablePreviews.set(preview.table.name, preview);
    }

    return {
      ...state,
      tablePreviews: newTablePreviews,
    };
  },
});

export { reducer, createActions, databasesAtom, useDatabaseActions };

export const dbTablePreviewsAtom = atom(
  (get) => get(databasesAtom).tablePreviews,
);
