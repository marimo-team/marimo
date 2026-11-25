/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { setNotebookAnalysis } from "@/__tests__/notebook-analysis";
import { MockExecutions } from "@/__mocks__/executions";
import { MockNotebook } from "@/__mocks__/notebook";
import { MockRequestClient } from "@/__mocks__/requests";
import { cellId } from "@/__tests__/branded";
import { store } from "@/core/state/jotai";
import {
  maybeAddAltairImport,
  maybeAddMarimoImport,
  maybeAddMissingImport,
} from "../add-missing-import";
import { notebookAtom } from "../cells";

// Mock the getRequestClient function
const mockRequestClient = MockRequestClient.create();
vi.mock("@/core/network/requests", () => ({
  getRequestClient: () => mockRequestClient,
}));

const Cell1 = cellId("1");
const Cell2 = cellId("2");

describe("maybeAddMissingImport", () => {
  beforeEach(() => {
    store.set(notebookAtom, MockNotebook.notebookState({ cellData: {} }));
  });

  it("skips the import when a cell declares the name", () => {
    const appStore = createStore();
    setNotebookAnalysis(appStore, { [Cell1]: { defs: ["mo"] } });
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
  it.each(VALID_IMPORTS)(
    "should not add an import if the import statement already exists in the notebook",
    (code) => {
      const appStore = createStore();

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
    },
  );

  it("adds a missing import even when the name is still bound in the kernel", () => {
    const appStore = createStore();
    MockExecutions.seed(appStore, [
      {
        ...MockExecutions.completed(Cell1),
        bindings: [{ name: "mo", type: "module", preview: "marimo" }],
      },
    ]);
    setNotebookAnalysis(appStore, { [Cell1]: { refs: ["mo"] } });

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
      store.set(
        notebookAtom,
        MockNotebook.notebookState({
          cellData: {
            [Cell1]: { code: "import marimo as mo" },
            [Cell2]: { code: "import altair as alt" },
          },
        }),
      );

      const createCell = vi.fn();
      const result = addImport({
        autoInstantiate: false,
        createCell,
        fromCellId: Cell1,
        before: false,
      });

      // Should not create a new cell since the import already exists
      expect(createCell).not.toHaveBeenCalled();
      expect(result).toBeNull();
    }
  });

  it("should create a marimo import before the source cell when requested", () => {
    const createCell = vi.fn();

    const result = maybeAddMarimoImport({
      autoInstantiate: false,
      createCell,
      fromCellId: Cell2,
      before: true,
    });

    expect(result).not.toBeNull();
    expect(createCell).toHaveBeenCalledWith(
      expect.objectContaining({
        before: Cell2,
        code: "import marimo as mo",
      }),
    );
  });
});
