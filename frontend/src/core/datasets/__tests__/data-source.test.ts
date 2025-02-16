/* Copyright 2024 Marimo. All rights reserved. */
import { expect, it, describe, beforeEach } from "vitest";
import {
  type ConnectionName,
  type DataSourceConnection,
  type DataSourceState,
  DEFAULT_ENGINE,
  exportedForTesting,
} from "../data-source-connections";
import type { VariableName } from "@/core/variables/types";

const { reducer, initialState } = exportedForTesting;

// Helper function to add connections
function addConnection(
  connections: DataSourceConnection[],
  state: DataSourceState,
): DataSourceState {
  return reducer(state, {
    type: "addDataSourceConnection",
    payload: {
      connections: connections,
    },
  });
}

describe("data source connections", () => {
  let state: DataSourceState;

  beforeEach(() => {
    state = initialState();
  });

  it("starts with default connections map", () => {
    expect(initialState().connectionsMap.size).toBe(1);
    expect(initialState().connectionsMap.has(DEFAULT_ENGINE)).toBe(true);
  });

  it("can add new connections", () => {
    const newConnections = [
      {
        name: "conn1" as ConnectionName,
        source: "sqlite",
        display_name: "SQLite DB",
        dialect: "sqlite",
        databases: [],
      },
    ];

    const newState = addConnection(newConnections, state);
    expect(newState.connectionsMap.size).toBe(2);
    expect(newState.connectionsMap.get("conn1" as ConnectionName)).toEqual(
      newConnections[0],
    );
  });

  it("updates existing connections", () => {
    const connection = {
      name: "conn1" as ConnectionName,
      source: "sqlite",
      display_name: "SQLite DB",
      dialect: "sqlite",
      databases: [],
    };

    const updatedConnection = {
      ...connection,
      display_name: "Updated SQLite",
    };

    let newState = addConnection([connection], state);
    newState = addConnection([updatedConnection], state);

    expect(newState.connectionsMap.size).toBe(2);
    expect(newState.connectionsMap.get("conn1" as ConnectionName)).toEqual(
      updatedConnection,
    );
  });

  it("can remove connections", () => {
    const connections = [
      {
        name: "conn1" as ConnectionName,
        source: "sqlite",
        display_name: "SQLite DB",
        dialect: "sqlite",
        databases: [],
      },
      {
        name: "conn2" as ConnectionName,
        source: "postgres",
        dialect: "postgres",
        display_name: "Postgres DB",
        databases: [],
      },
    ];

    let newState = addConnection(connections, state);
    expect(newState.connectionsMap.size).toBe(3);

    newState = reducer(newState, {
      type: "removeDataSourceConnection",
      payload: "conn1" as ConnectionName,
    });
    expect(newState.connectionsMap.size).toBe(2);
    expect(newState.connectionsMap.has("conn2" as ConnectionName)).toBe(true);
  });

  it("can clear all connections", () => {
    const connections = [
      {
        name: "conn1" as ConnectionName,
        source: "sqlite",
        display_name: "SQLite DB",
        dialect: "sqlite",
        databases: [],
      },
      {
        name: "conn2" as ConnectionName,
        source: "postgres",
        display_name: "Postgres DB",
        dialect: "postgres",
        databases: [],
      },
    ];

    let newState = addConnection(connections, state);
    expect(newState.connectionsMap.size).toBe(3);

    newState = reducer(newState, {
      type: "clearDataSourceConnections",
      payload: {},
    });
    expect(newState.connectionsMap.size).toBe(0);
  });
});

describe("filtering data sources", () => {
  // helper function to filter data sources by variable names
  function filterDataSources(payload: VariableName[]) {
    return reducer(baseState, {
      type: "filterDataSourcesFromVariables",
      payload: payload,
    });
  }

  const connections = [
    {
      name: "conn1" as ConnectionName,
      source: "sqlite",
      display_name: "SQLite DB",
      dialect: "sqlite",
      databases: [],
    },
    {
      name: "conn2" as ConnectionName,
      source: "postgres",
      display_name: "Postgres DB",
      dialect: "postgres",
      databases: [],
    },
  ];

  let baseState: DataSourceState;

  beforeEach(() => {
    baseState = addConnection(connections, baseState);
    expect(baseState.connectionsMap.size).toBe(3); // 2 + 1 (default) connections
  });

  it("keeps only DEFAULT_ENGINE when no variables", () => {
    const filtered = filterDataSources([]);
    expect(filtered.connectionsMap.size).toBe(1);
    expect(filtered.connectionsMap.has(DEFAULT_ENGINE)).toBe(true);
  });

  it("keeps matching variables and DEFAULT_ENGINE", () => {
    const filtered = filterDataSources(["conn1" as unknown as VariableName]);
    expect(filtered.connectionsMap.size).toBe(2);
    expect(filtered.connectionsMap.has("conn1" as ConnectionName)).toBe(true);
    expect(filtered.connectionsMap.has(DEFAULT_ENGINE)).toBe(true);
  });

  it("filters out non-matching variables", () => {
    const filtered = filterDataSources([
      "non_existent" as unknown as VariableName,
    ]);
    expect(filtered.connectionsMap.size).toBe(1);
  });

  it("handles mix of matching and non-matching variables", () => {
    const filtered = filterDataSources([
      "conn1" as unknown as VariableName,
      "non_existent" as unknown as VariableName,
    ]);
    expect(filtered.connectionsMap.size).toBe(2);
    expect(filtered.connectionsMap.has("conn1" as ConnectionName)).toBe(true);
    expect(filtered.connectionsMap.has(DEFAULT_ENGINE)).toBe(true);
  });
});
