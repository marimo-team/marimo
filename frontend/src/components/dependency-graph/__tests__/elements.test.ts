/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { CellId } from "@/core/cells/ids";
import type { Variable, VariableName, Variables } from "@/core/variables/types";
import {
  collapsedNodeWidth,
  computeDefsByCell,
  isStateFlowVariable,
  wrapDefs,
} from "../elements";

const names = (list: string[]) => list as VariableName[];

function variable(
  partial: Omit<Partial<Variable>, "name"> & { name: string },
): Variable {
  return {
    declaredBy: [],
    usedBy: [],
    ...partial,
    name: partial.name as VariableName,
  };
}

describe("collapsedNodeWidth", () => {
  it("clamps short labels to the minimum width", () => {
    expect(collapsedNodeWidth("")).toBe(90);
    expect(collapsedNodeWidth("x")).toBe(90);
  });

  it("clamps long labels to the maximum width", () => {
    expect(collapsedNodeWidth("a".repeat(100))).toBe(240);
  });

  it("scales with label length between the bounds", () => {
    const width = collapsedNodeWidth("df, summary");
    expect(width).toBeGreaterThan(90);
    expect(width).toBeLessThan(240);
  });
});

describe("isStateFlowVariable", () => {
  it("flags State and SetFunctor (from mo.state)", () => {
    expect(
      isStateFlowVariable(variable({ name: "g", dataType: "State" })),
    ).toBe(true);
    expect(
      isStateFlowVariable(variable({ name: "s", dataType: "SetFunctor" })),
    ).toBe(true);
  });

  it("does not flag UI elements or plain values", () => {
    // UIElement is frontend-driven / immutable during a run — not a state flow.
    expect(
      isStateFlowVariable(variable({ name: "sl", dataType: "slider" })),
    ).toBe(false);
    expect(isStateFlowVariable(variable({ name: "n", dataType: "int" }))).toBe(
      false,
    );
    expect(isStateFlowVariable(variable({ name: "u", dataType: null }))).toBe(
      false,
    );
    expect(isStateFlowVariable(variable({ name: "u2" }))).toBe(false);
  });
});

describe("wrapDefs", () => {
  it("packs short names to the 12-char minimum budget", () => {
    expect(
      wrapDefs(names(["np", "math", "time", "io", "numpy", "pandas"])),
    ).toEqual(["np, math", "time, io", "numpy", "pandas"]);
  });

  it("gives a long name its own line, then packs the rest to its width", () => {
    expect(
      wrapDefs(
        names([
          "very_very_very_long_variable_name",
          "short_var",
          "shr_v",
          "io",
          "numpy",
          "wev",
        ]),
      ),
    ).toEqual([
      "very_very_very_long_variable_name",
      "short_var, shr_v, io, numpy, wev",
    ]);
  });

  it("returns an empty list for no defs", () => {
    expect(wrapDefs(names([]))).toEqual([]);
  });
});

describe("computeDefsByCell", () => {
  it("maps each cell to the variables it declares", () => {
    const c1 = "c1" as CellId;
    const c2 = "c2" as CellId;
    const a = "a" as VariableName;
    const b = "b" as VariableName;
    const c = "c" as VariableName;
    const variables: Variables = {
      [a]: variable({ name: a, declaredBy: [c1], usedBy: [c2] }),
      [b]: variable({ name: b, declaredBy: [c1] }),
      [c]: variable({ name: c, declaredBy: [c2] }),
    };
    const defs = computeDefsByCell(variables);
    expect(defs.get(c1)).toEqual([a, b]);
    expect(defs.get(c2)).toEqual([c]);
  });

  it("returns an empty map when there are no variables", () => {
    expect(computeDefsByCell({}).size).toBe(0);
  });
});
