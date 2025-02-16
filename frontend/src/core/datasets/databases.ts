/* Copyright 2024 Marimo. All rights reserved. */
import { createReducerAndAtoms } from "@/utils/createReducer";
import type { Database, SQLTablePreview } from "../kernel/messages";
import { atom } from "jotai";
import type { VariableName } from "../variables/types";
import { DEFAULT_ENGINE } from "./data-source-connections";

export interface EnginesState {
  // Engine names are unique. Within an engine, database names are unique
  enginesMap: ReadonlyMap<string, ReadonlyMap<string, Database>>;
}

export function initialState(): EnginesState {
  return {
    enginesMap: new Map(),
  };
}

const {
  reducer,
  createActions,
  valueAtom: enginesAtom,
  useActions: useDatabaseActions,
} = createReducerAndAtoms(initialState, {
  addDatabase: (
    state: EnginesState,
    opts: { databases: Database[] },
  ): EnginesState => {
    if (opts.databases.length === 0) {
      return state;
    }

    const newEnginesMap = new Map(state.enginesMap);
    for (const db of opts.databases) {
      const engine = db.engine || DEFAULT_ENGINE;
      const newDatabasesMap = new Map(newEnginesMap.get(engine) || new Map());
      newDatabasesMap.set(db.name, db);
      newEnginesMap.set(engine, newDatabasesMap);
    }

    return {
      ...state,
      enginesMap: newEnginesMap,
    };
  },

  filterEnginesFromVariables: (
    state: EnginesState,
    variableNames: VariableName[],
  ) => {
    // VariableNames contain engine names
    const names = new Set(variableNames);

    const newEnginesMap = new Map(
      [...state.enginesMap].filter(([name]) => {
        if (name === DEFAULT_ENGINE) {
          return true;
        }
        return names.has(name as unknown as VariableName);
      }),
    );

    return {
      ...state,
      enginesMap: newEnginesMap,
    };
  },
});

export { reducer, createActions, enginesAtom, useDatabaseActions };

// Hook to get & persist SQL table previews
export const tablePreviewsAtom = atom<ReadonlyMap<string, SQLTablePreview>>(
  new Map<string, SQLTablePreview>(),
);
