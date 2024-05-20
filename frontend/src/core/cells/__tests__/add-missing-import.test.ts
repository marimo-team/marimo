/* Copyright 2024 Marimo. All rights reserved. */
import { variablesAtom } from "@/core/variables/state";
import { createStore } from "jotai";
import { it, describe, expect, vi } from "vitest";
import { maybeAddMissingImport } from "../add-missing-import";
import type { Variables } from "@/core/variables/types";
import { type NotebookState, notebookAtom } from "../cells";
import type { CellId } from "../ids";
import type { CellData } from "../types";

const CELL_IDS = ["1" as CellId];

describe("maybeAddMissingImport", () => {
  it("should not add an import if the variable is already in the variables state", () => {
    const appStore = createStore();
    appStore.set(variablesAtom, { mo: {} } as Variables);
    const onAddImport = vi.fn();
    maybeAddMissingImport("marimo", "mo", onAddImport, appStore);
    expect(onAddImport).not.toHaveBeenCalled();
  });

  const VALID_IMPORTS = [
    "import marimo as mo",
    "import marimo as mo\nimport marimo as mo",
    "import   marimo    as   mo",
  ];
  it.each(VALID_IMPORTS)(
    "should not add an import if the import statement already exists in the notebook",
    (code) => {
      const appStore = createStore();
      appStore.set(variablesAtom, {} as Variables);
      appStore.set(notebookAtom, {
        cellData: {
          ["1" as CellId]: {
            code: code,
          } as CellData,
        },
        cellIds: CELL_IDS,
      } as NotebookState);
      const onAddImport = vi.fn();
      maybeAddMissingImport("marimo", "mo", onAddImport, appStore);
      expect(onAddImport).not.toHaveBeenCalled();
    },
  );

  it("should add an import if the variable is not in the variables state and the import statement does not exist in the notebook", () => {
    const appStore = createStore();
    appStore.set(variablesAtom, {} as Variables);
    appStore.set(notebookAtom, {
      cellData: {
        ["1" as CellId]: {
          code: "mo.md('hello')",
        } as CellData,
      },
      cellIds: CELL_IDS,
    } as NotebookState);
    const onAddImport = vi.fn();
    maybeAddMissingImport("marimo", "mo", onAddImport, appStore);
    expect(onAddImport).toHaveBeenCalledWith("import marimo as mo");
  });
});
