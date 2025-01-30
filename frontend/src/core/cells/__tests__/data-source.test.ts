/* Copyright 2024 Marimo. All rights reserved. */
import { expect, it, describe, beforeEach } from "vitest";
import {
  type ConnectionName,
  type DataSourceConnection,
  type DataSourceState,
  exportedForTesting,
} from "../data-source-connections";

const { reducer, initialState } = exportedForTesting;

describe("data source connections", () => {
  let state: DataSourceState;

  // helper function to add connections
  function addConnection(connections: DataSourceConnection[]): DataSourceState {
    return reducer(state, {
      type: "addDataSourceConnection",
      payload: {
        connections: connections,
      },
    });
  }

  beforeEach(() => {
    state = initialState();
  });

  it("starts with empty connections map", () => {
    expect(initialState().connectionsMap.size).toBe(1);
  });

  it("can add new connections", () => {
    const newConnections = [
      {
        name: "conn1" as ConnectionName,
        source: "sqlite",
        display_name: "SQLite DB",
        dialect: "sqlite",
      },
    ];

    const newState = addConnection(newConnections);
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
    };

    const updatedConnection = {
      ...connection,
      display_name: "Updated SQLite",
    };

    let newState = addConnection([connection]);
    newState = addConnection([updatedConnection]);

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
      },
      {
        name: "conn2" as ConnectionName,
        source: "postgres",
        dialect: "postgres",
        display_name: "Postgres DB",
      },
    ];

    let newState = addConnection(connections);
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
      },
      {
        name: "conn2" as ConnectionName,
        source: "postgres",
        display_name: "Postgres DB",
        dialect: "postgres",
      },
    ];

    let newState = addConnection(connections);
    expect(newState.connectionsMap.size).toBe(3);

    newState = reducer(newState, {
      type: "clearDataSourceConnections",
      payload: {},
    });
    expect(newState.connectionsMap.size).toBe(0);
  });
});
