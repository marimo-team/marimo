/* Copyright 2024 Marimo. All rights reserved. */
import { createReducerAndAtoms } from "@/utils/createReducer";
import type { TypedString } from "@/utils/typed";

export type ConnectionName = TypedString<"ConnectionName">;

export interface DataSourceConnection {
  // Backend will dedupe by name & keep the latest, so we use this as the key
  name: ConnectionName;
  source: string;
  display_name?: string;
  dialect: string;
}

export interface DataSourceState {
  connectionsMap: Map<ConnectionName, DataSourceConnection>;
}

function initialState(): DataSourceState {
  return {
    connectionsMap: new Map(),
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
    const newConnections = opts.connections;

    for (const newConn of newConnections) {
      const existingConnection = state.connectionsMap.get(newConn.name);
      if (existingConnection) {
        // update the existing connection
        state.connectionsMap.set(existingConnection.name, newConn);
      } else {
        state.connectionsMap.set(newConn.name, newConn);
      }
    }

    return state;
  },
  clearDataSourceConnections: (): DataSourceState => ({
    connectionsMap: new Map(),
  }),
  removeDataSourceConnection: (
    state: DataSourceState,
    connectionName: ConnectionName,
  ): DataSourceState => {
    state.connectionsMap.delete(connectionName);
    return state;
  },
});

export { dataSourceConnectionsAtom, useDataSourceActions };

export const exportedForTesting = {
  reducer,
  createActions,
  initialState,
};
