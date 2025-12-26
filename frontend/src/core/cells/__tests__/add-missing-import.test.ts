/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { MockRequestClient } from "@/__mocks__/requests";
import { store } from "@/core/state/jotai";
import { variablesAtom } from "@/core/variables/state";
import type { Variables } from "@/core/variables/types";
import {
  maybeAddAltairImport,
  maybeAddMarimoImport,
  maybeAddMissingImport,
} from "../add-missing-import";
import { notebookAtom } from "../cells";
import type { CellId } from "../ids";

// Mock the getRequestClient function
const mockRequestClient = MockRequestClient.create();
vi.mock("@/core/network/requests", () => ({
  getRequestClient: () => mockRequestClient,
}));

const Cell1 = "1" as CellId;
const Cell2 = "2" as CellId;

describe("maybeAddMissingImport", () => {
  beforeEach(() => {
    store.set(variablesAtom, {} as Variables);
    store.set(notebookAtom, MockNotebook.notebookState({ cellData: {} }));
  });

  it("should not add an import if the variable is already in the variables state", () => {
    const appStore = createStore();
    appStore.set(variablesAtom, { mo: {} } as Variables);
    const onAddImport = vi.fn();
    maybeAddMissingImport({
      moduleName: "marimo",
      variableName: "mo",
      onAddImport,
      appStore,
    });
    expect(onAddImport).not.toHaveBeenCalled();
  });

  const VALID_IMPORTS = [
    "import marimo as mo",
    "import marimo as mo\nimport marimo as mo",
    "import   marimo    as   mo",
  ];
  it.each(
    VALID_IMPORTS,
  )("should not add an import if the import statement already exists in the notebook", (code) => {
    const appStore = createStore();
    appStore.set(variablesAtom, {} as Variables);
    appStore.set(
      notebookAtom,
      MockNotebook.notebookState({
        cellData: {
          [Cell1]: { code: code },
        },
      }),
    );
    const onAddImport = vi.fn();
    maybeAddMissingImport({
      moduleName: "marimo",
      variableName: "mo",
      onAddImport,
      appStore,
    });
    expect(onAddImport).not.toHaveBeenCalled();
  });

  it("should add an import if the variable is not in the variables state and the import statement does not exist in the notebook", () => {
    const appStore = createStore();
    appStore.set(variablesAtom, {} as Variables);
    appStore.set(
      notebookAtom,
      MockNotebook.notebookState({
        cellData: {
          [Cell1]: { code: "mo.md('hello')" },
        },
      }),
    );
    const onAddImport = vi.fn();
    maybeAddMissingImport({
      moduleName: "marimo",
      variableName: "mo",
      onAddImport,
      appStore,
    });
    expect(onAddImport).toHaveBeenCalledWith("import marimo as mo");
  });

  it("should not create a new cell if import already exists due to skipIfCodeExists", () => {
    const addImports = [maybeAddMarimoImport, maybeAddAltairImport];
    for (const addImport of addImports) {
      store.set(variablesAtom, {} as Variables);
      store.set(
        notebookAtom,
        MockNotebook.notebookState({
          cellData: {
            [Cell1]: { code: "import marimo as mo" },
            [Cell2]: { code: "import altair as alt" },
          },
        }),
      );

      const createNewCell = vi.fn();
      const result = addImport({
        autoInstantiate: false,
        createNewCell,
        fromCellId: Cell1,
        before: false,
      });

      // Should not create a new cell since the import already exists
      expect(createNewCell).not.toHaveBeenCalled();
      expect(result).toBeNull();
    }
  });
});
