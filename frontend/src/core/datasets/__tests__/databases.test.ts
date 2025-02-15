/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect, beforeEach } from "vitest";
import { reducer } from "../databases";
import { type EnginesState, initialState } from "../databases";
import type { Database } from "../../kernel/messages";
import { DEFAULT_ENGINE } from "../data-source-connections";
import type { VariableName } from "@/core/variables/types";

const filterVariablesOpName = "filterEnginesFromVariables";

// Helper function to add databases
function addDatabase(databases: Database[], state: EnginesState): EnginesState {
  return reducer(state, {
    type: "addDatabase",
    payload: {
      databases,
    },
  });
}

describe("databases", () => {
  let state: EnginesState;

  beforeEach(() => {
    state = initialState();
  });

  it("starts with empty engines map", () => {
    expect(state.enginesMap.size).toBe(0);
  });

  it("can add new databases", () => {
    const databases: Database[] = [
      {
        name: "db1",
        engine: "engine1",
        dialect: "",
        schemas: [],
      },
      {
        name: "db2",
        engine: "engine2",
        dialect: "",
        schemas: [],
      },
    ];

    const newState = addDatabase(databases, state);
    expect(newState.enginesMap.size).toBe(2);
    expect(newState.enginesMap.get("engine1")?.size).toBe(1);
    expect(newState.enginesMap.get("engine2")?.size).toBe(1);

    expect(newState.enginesMap.get("engine1")?.get("db1")).toEqual(
      databases[0],
    );
    expect(newState.enginesMap.get("engine2")?.get("db2")).toEqual(
      databases[1],
    );
  });

  it("should overwrite the same database with the same engine name", () => {
    const databases: Database[] = [
      {
        name: "db1",
        engine: "engine1",
        dialect: "",
        schemas: [],
      },
      {
        name: "db1",
        engine: "engine2",
        dialect: "",
        schemas: [],
      },
    ];

    const newState = addDatabase(databases, state);
    expect(newState.enginesMap.size).toBe(2);

    const updatedDatabases: Database[] = [
      {
        name: "db1",
        engine: "engine1",
        dialect: "",
        schemas: [],
      },
    ];

    const updatedState = addDatabase(updatedDatabases, newState);
    expect(updatedState.enginesMap.size).toBe(2);
    expect(updatedState.enginesMap.get("engine1")?.size).toBe(1);
    expect(updatedState.enginesMap.get("engine1")?.get("db1")).toEqual(
      updatedDatabases[0],
    );
  });

  it("should add databases to the default engine if engine is not specified", () => {
    const databases: Database[] = [
      {
        name: "db1",
        engine: "",
        dialect: "",
        schemas: [],
      },
    ];

    const newState = addDatabase(databases, state);
    expect(newState.enginesMap.size).toBe(1);
    expect(newState.enginesMap.get(DEFAULT_ENGINE)?.size).toBe(1);
    expect(newState.enginesMap.get(DEFAULT_ENGINE)?.get("db1")).toEqual(
      databases[0],
    );

    const updatedDatabases: Database[] = [
      {
        name: "db2",
        engine: "",
        dialect: "",
        schemas: [],
      },
    ];

    const updatedState = addDatabase(updatedDatabases, newState);
    expect(updatedState.enginesMap.size).toBe(1);
    expect(updatedState.enginesMap.get(DEFAULT_ENGINE)?.size).toBe(2);
    expect(updatedState.enginesMap.get(DEFAULT_ENGINE)?.get("db2")).toEqual(
      updatedDatabases[0],
    );
  });

  it("should handle adding databases with mixed specified and unspecified engines", () => {
    const databases: Database[] = [
      {
        name: "db1",
        engine: "",
        dialect: "",
        schemas: [],
      },
      {
        name: "db2",
        engine: "engine1",
        dialect: "",
        schemas: [],
      },
    ];

    const newState = addDatabase(databases, state);
    expect(newState.enginesMap.size).toBe(2);
    expect(newState.enginesMap.get(DEFAULT_ENGINE)?.size).toBe(1);
    expect(newState.enginesMap.get("engine1")?.size).toBe(1);
  });

  it("should filter databases based on variable names", () => {
    const databases: Database[] = [
      {
        name: "db1",
        engine: "engine1",
        dialect: "",
        schemas: [],
      },
      {
        name: "db2",
        engine: "engine2",
        dialect: "",
        schemas: [],
      },
      {
        name: "db3",
        engine: "engine2",
        dialect: "",
        schemas: [],
      },
      {
        name: "db3",
        engine: "engine3",
        dialect: "",
        schemas: [],
      },
    ];

    let newState = addDatabase(databases, state);
    expect(newState.enginesMap.size).toBe(3);

    const variableNames = ["engine1", "engine3"];
    newState = reducer(newState, {
      type: filterVariablesOpName,
      payload: variableNames,
    });

    expect(newState.enginesMap.size).toBe(2);
    expect(newState.enginesMap.has("engine1")).toBe(true);
    expect(newState.enginesMap.has("engine3")).toBe(true);
    expect(newState.enginesMap.has("engine2")).toBe(false);

    expect(newState.enginesMap.get("engine1")?.size).toBe(1);
    expect(newState.enginesMap.get("engine3")?.size).toBe(1);
  });

  it("should filter out all engines except the default engine if no variable names match", () => {
    const databases: Database[] = [
      {
        name: "db1",
        engine: "",
        dialect: "",
        schemas: [],
      },
      {
        name: "db2",
        engine: "engine1",
        dialect: "",
        schemas: [],
      },
      {
        name: "db3",
        engine: "engine2",
        dialect: "",
        schemas: [],
      },
    ];

    let newState = addDatabase(databases, state);
    expect(newState.enginesMap.size).toBe(3);

    const variableNames: VariableName[] = [];
    newState = reducer(newState, {
      type: filterVariablesOpName,
      payload: variableNames,
    });

    expect(newState.enginesMap.size).toBe(1);
    expect(newState.enginesMap.has(DEFAULT_ENGINE)).toBe(true);
    expect(newState.enginesMap.has("engine1")).toBe(false);
    expect(newState.enginesMap.has("engine2")).toBe(false);
  });

  it("should handle filtering when no databases are present", () => {
    const variableNames = ["engine1", "engine2"];
    const newState = reducer(state, {
      type: filterVariablesOpName,
      payload: variableNames,
    });

    expect(newState.enginesMap.size).toBe(0);
  });

  it("should not filter when all variables are present", () => {
    const databases: Database[] = [
      {
        name: "db1",
        engine: "engine1",
        dialect: "",
        schemas: [],
      },
      {
        name: "db2",
        engine: "engine2",
        dialect: "",
        schemas: [],
      },
    ];

    let newState = addDatabase(databases, state);
    expect(newState.enginesMap.size).toBe(2);

    const variableNames = ["engine1", "engine2"];
    newState = reducer(newState, {
      type: filterVariablesOpName,
      payload: variableNames,
    });

    expect(newState.enginesMap.size).toBe(2);
    expect(newState.enginesMap.has("engine1")).toBe(true);
    expect(newState.enginesMap.has("engine2")).toBe(true);
  });
});
