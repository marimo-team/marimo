/* Copyright 2024 Marimo. All rights reserved. */
import { createReducerAndAtoms } from "@/utils/createReducer";
import type { TypedString } from "@/utils/typed";
import { DEFAULT_ENGINE } from "../codemirror/language/sql";
import type { VariableName } from "../variables/types";

export type ConnectionName = TypedString<"ConnectionName">;

export interface DataSourceConnection {
  name: ConnectionName;
  source: string;
  display_name: string;
  dialect: string;
}

export interface DataSourceState {
  connectionsMap: ReadonlyMap<ConnectionName, DataSourceConnection>;
}

function initialState(): DataSourceState {
  return {
    connectionsMap: new Map().set(DEFAULT_ENGINE, {
      name: DEFAULT_ENGINE,
      source: "duckdb",
      dialect: "duckdb",
      display_name: "DuckDB In-Memory",
    }),
  };
}

const {
  reducer,
  createActions,
  valueAtom: dataSourceConnectionsAtom,
  useActions: useDataSourceActions,
} = createReducerAndAtoms(initialState, {
  addDataSourceConnection: (
    state: DataSourceState,
    opts: { connections: DataSourceConnection[] },
  ): DataSourceState => {
    if (opts.connections.length === 0) {
      return state;
    }

    // update existing connections with latest values
    // add new ones if they don't exist
    // Backend will dedupe by connection name & keep the latest, so we use this as the key
    const newMap = new Map(state.connectionsMap);
    for (const conn of opts.connections) {
      newMap.set(conn.name, conn);
    }

    return { connectionsMap: newMap };
  },

  // Keep default engine and any connections that are used by variables
  filterDataSourcesFromVariables: (
    state: DataSourceState,
    variableNames: VariableName[],
  ) => {
    const newMap = new Map(
      [...state.connectionsMap].filter(
        ([name]) =>
          name === DEFAULT_ENGINE ||
          variableNames.includes(name as unknown as VariableName),
      ),
    );
    return { connectionsMap: newMap };
  },

  clearDataSourceConnections: (): DataSourceState => ({
    connectionsMap: new Map(),
  }),

  removeDataSourceConnection: (
    state: DataSourceState,
    connectionName: ConnectionName,
  ): DataSourceState => {
    const newMap = new Map(state.connectionsMap);
    newMap.delete(connectionName);
    return { connectionsMap: newMap };
  },
});

export { dataSourceConnectionsAtom, useDataSourceActions };

export const exportedForTesting = {
  reducer,
  createActions,
  initialState,
};
