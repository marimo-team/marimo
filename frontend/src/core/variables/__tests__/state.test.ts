/* Copyright 2024 Marimo. All rights reserved. */
import { beforeEach, describe, expect, it } from "vitest";
import type { CellId } from "@/core/cells/ids";
import { exportedForTesting } from "../state";
import type { VariableName, Variables } from "../types";

const { initialState, reducer, createActions } = exportedForTesting;

const CellIds = {
  a: "a" as CellId,
  b: "b" as CellId,
};

const Names = {
  x: "x" as VariableName,
  y: "y" as VariableName,
};

describe("cell reducer", () => {
  let state: Variables;

  const actions = createActions((action) => {
    state = reducer(state, action);
  });

  beforeEach(() => {
    state = initialState();
  });

  it("should set variables", () => {
    const x = {
      name: Names.x,
      declaredBy: [CellIds.a],
      usedBy: [CellIds.b],
    };
    const variables: Variables = {
      [Names.x]: x,
    };
    actions.setVariables([x]);
    expect(state).toEqual(variables);
  });

  it("should clear variables", () => {
    const x = {
      name: Names.x,
      declaredBy: [CellIds.a],
      usedBy: [CellIds.b],
    };
    const variables: Variables = {
      [Names.x]: x,
    };
    actions.setVariables([x]);
    expect(state).toEqual(variables);

    actions.setVariables([]);
    expect(state).toEqual({});
  });


  it("should add variables", () => {
    const x = {
      name: Names.x,
      declaredBy: [CellIds.a],
      usedBy: [CellIds.b],
    };
    const y = {
      name: Names.y,
      declaredBy: [CellIds.a],
      usedBy: [CellIds.b],
    };
    actions.addVariables([x, y]);
    expect(state).toEqual({
      [Names.x]: x,
      [Names.y]: y,
    });
  });

  it("should set metadata", () => {
    const x = {
      name: Names.x,
      declaredBy: [CellIds.a],
      usedBy: [CellIds.b],
    };
    const variables: Variables = {
      [Names.x]: x,
    };
    actions.setVariables([x]);
    expect(state).toEqual(variables);

    // add metadata
    actions.setMetadata([
      {
        name: Names.x,
        value: "1",
        dataType: "number",
      },
    ]);
    expect(state).toEqual({
      [Names.x]: {
        name: Names.x,
        declaredBy: [CellIds.a],
        usedBy: [CellIds.b],
        value: "1",
        dataType: "number",
      },
    });

    // drop unknown metadata
    actions.setMetadata([
      {
        name: Names.x,
        value: "2",
        dataType: "number",
      },
      {
        name: Names.y,
        value: "3",
        dataType: "number",
      },
    ]);
    expect(state).toEqual({
      [Names.x]: {
        name: Names.x,
        declaredBy: [CellIds.a],
        usedBy: [CellIds.b],
        value: "2",
        dataType: "number",
      },
    });

    // can re-add variables
    actions.addVariables([
      {
        name: Names.x,
        declaredBy: [CellIds.a],
        usedBy: [],
      },
    ]);
    expect(state).toEqual({
      [Names.x]: {
        name: Names.x,
        declaredBy: [CellIds.a],
        usedBy: [],
        value: "2",
        dataType: "number",
      },
    });
  });
});
