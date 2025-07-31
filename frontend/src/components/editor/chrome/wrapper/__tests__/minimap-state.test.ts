/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import type { CellId } from "@/core/cells/ids";
import type { VariableName, Variables } from "@/core/variables/types";
import { buildCellGraph } from "../minimap-state";

const cellId = (id: string) => id as CellId;
const varName = (name: string) => name as VariableName;

describe("buildCellGraph", () => {
  it("builds graph for simple linear dependency", () => {
    // cell1 declares x, cell2 uses x
    const cellIds = [cellId("cell1"), cellId("cell2")];
    const variables: Variables = {
      [varName("x")]: {
        name: varName("x"),
        declaredBy: [cellId("cell1")],
        usedBy: [cellId("cell2")],
      },
    };

    const graph = buildCellGraph(cellIds, variables);

    expect(graph).toMatchInlineSnapshot(`
      {
        "cell1": {
          "ancestors": Set {},
          "children": Set {
            "cell2",
          },
          "descendants": Set {
            "cell2",
          },
          "parents": Set {},
          "variables": [
            "x",
          ],
        },
        "cell2": {
          "ancestors": Set {
            "cell1",
          },
          "children": Set {},
          "descendants": Set {},
          "parents": Set {
            "cell1",
          },
          "variables": [],
        },
      }
    `);
  });

  it("builds graph for diamond pattern", () => {
    // cell1 declares x
    // cell2 and cell3 both use x and declare y and z
    // cell4 uses y and z
    const cellIds = [
      cellId("cell1"),
      cellId("cell2"),
      cellId("cell3"),
      cellId("cell4"),
    ];
    const variables: Variables = {
      [varName("x")]: {
        name: varName("x"),
        declaredBy: [cellId("cell1")],
        usedBy: [cellId("cell2"), cellId("cell3")],
      },
      [varName("y")]: {
        name: varName("y"),
        declaredBy: [cellId("cell2")],
        usedBy: [cellId("cell4")],
      },
      [varName("z")]: {
        name: varName("z"),
        declaredBy: [cellId("cell3")],
        usedBy: [cellId("cell4")],
      },
    };

    const graph = buildCellGraph(cellIds, variables);

    expect(graph).toMatchInlineSnapshot(`
      {
        "cell1": {
          "ancestors": Set {},
          "children": Set {
            "cell2",
            "cell3",
          },
          "descendants": Set {
            "cell2",
            "cell4",
            "cell3",
          },
          "parents": Set {},
          "variables": [
            "x",
          ],
        },
        "cell2": {
          "ancestors": Set {
            "cell1",
          },
          "children": Set {
            "cell4",
          },
          "descendants": Set {
            "cell4",
          },
          "parents": Set {
            "cell1",
          },
          "variables": [
            "y",
          ],
        },
        "cell3": {
          "ancestors": Set {
            "cell1",
          },
          "children": Set {
            "cell4",
          },
          "descendants": Set {
            "cell4",
          },
          "parents": Set {
            "cell1",
          },
          "variables": [
            "z",
          ],
        },
        "cell4": {
          "ancestors": Set {
            "cell2",
            "cell1",
            "cell3",
          },
          "children": Set {},
          "descendants": Set {},
          "parents": Set {
            "cell2",
            "cell3",
          },
          "variables": [],
        },
      }
    `);
  });

  it("handles self-referencing and isolated cells", () => {
    const cellIds = [cellId("cell1"), cellId("cell2"), cellId("cell3")];
    const variables: Variables = {
      [varName("x")]: {
        name: varName("x"),
        declaredBy: [cellId("cell1")],
        usedBy: [cellId("cell1"), cellId("cell2")], // self-reference + downstream
      },
      [varName("y")]: {
        name: varName("y"),
        declaredBy: [cellId("cell3")],
        usedBy: [], // isolated variable
      },
    };

    const graph = buildCellGraph(cellIds, variables);

    expect(graph).toMatchInlineSnapshot(`
      {
        "cell1": {
          "ancestors": Set {},
          "children": Set {
            "cell2",
          },
          "descendants": Set {
            "cell2",
          },
          "parents": Set {},
          "variables": [
            "x",
          ],
        },
        "cell2": {
          "ancestors": Set {
            "cell1",
          },
          "children": Set {},
          "descendants": Set {},
          "parents": Set {
            "cell1",
          },
          "variables": [],
        },
        "cell3": {
          "ancestors": Set {},
          "children": Set {},
          "descendants": Set {},
          "parents": Set {},
          "variables": [
            "y",
          ],
        },
      }
    `);
  });
});
