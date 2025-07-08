/* Copyright 2024 Marimo. All rights reserved. */

import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { describe, expect, it } from "vitest";
import { notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import { store } from "@/core/state/jotai";
import { variablesAtom } from "@/core/variables/state";
import type { VariableName, Variables } from "@/core/variables/types";
import { MultiColumn } from "@/utils/id-tree";
import { cellConfigExtension } from "../../config/extension";
import { adaptiveLanguageConfiguration } from "../../language/extension";
import { getCodes, getTopologicalCellIds } from "../getCodes";

const Cells = {
  cell1: "cell1" as CellId,
  cell2: "cell2" as CellId,
  cell3: "cell3" as CellId,
  cell4: "cell4" as CellId,
};

const Variables = {
  var1: "var1" as VariableName,
  var2: "var2" as VariableName,
  var3: "var3" as VariableName,
};

function createMockEditorView(code: string) {
  const view = new EditorView({
    state: EditorState.create({
      doc: code,
      extensions: [
        adaptiveLanguageConfiguration({
          cellId: "cell1" as CellId,
          completionConfig: {
            copilot: false,
            activate_on_typing: true,
            codeium_api_key: null,
          },
          hotkeys: new OverridingHotkeyProvider({}),
          placeholderType: "marimo-import",
          lspConfig: {},
        }),
        cellConfigExtension({
          completionConfig: {
            copilot: false,
            activate_on_typing: true,
            codeium_api_key: null,
          },
          hotkeys: new OverridingHotkeyProvider({}),
          placeholderType: "marimo-import",
          lspConfig: {},
          diagnosticsConfig: {},
        }),
      ],
    }),
  });

  return {
    editorView: view,
    editorViewOrNull: view,
  };
}

describe("getTopologicalCellIds", () => {
  it("should return topologically sorted cell IDs", () => {
    // Setup mock data
    store.set(notebookAtom, {
      cellIds: MultiColumn.from([
        [Cells.cell1, Cells.cell2, Cells.cell3, Cells.cell4],
      ]),
      cellData: {},
      cellRuntime: {},
      cellHandles: {},
      history: [],
      scrollKey: null,
      cellLogs: [],
    });
    const variables: Variables = {
      [Variables.var1]: {
        name: Variables.var1,
        declaredBy: [Cells.cell1],
        usedBy: [Cells.cell2, Cells.cell3],
      },
      [Variables.var2]: {
        name: Variables.var2,
        declaredBy: [Cells.cell2],
        usedBy: [Cells.cell4],
      },
      [Variables.var3]: {
        name: Variables.var3,
        declaredBy: [Cells.cell3],
        usedBy: [],
      },
    };
    store.set(variablesAtom, variables);

    // Call the function
    const result = getTopologicalCellIds();

    // Assert the result
    expect(result).toEqual(["cell1", "cell2", "cell3", "cell4"]);
  });
});

describe("getCodes", () => {
  it("should return only the otherCode when there are no other cells", () => {
    store.set(notebookAtom, {
      cellIds: MultiColumn.from([[]]),
      cellData: {},
      cellRuntime: {},
      cellHandles: {},
      history: [],
      scrollKey: null,
      cellLogs: [],
    });
    const otherCode = "print('Hello World')";
    const result = getCodes(otherCode);
    expect(result).toEqual("print('Hello World')");
  });

  it("should concatenate codes from multiple cells", () => {
    const otherCode = "print('Hello World')";
    const mockEditorViews = [
      createMockEditorView("import os"),
      createMockEditorView("x = 1"),
    ];
    store.set(notebookAtom, {
      cellIds: MultiColumn.from([[Cells.cell1, Cells.cell2]]),
      cellData: {},
      cellRuntime: {},
      cellHandles: {
        [Cells.cell1]: { current: mockEditorViews[0] },
        [Cells.cell2]: { current: mockEditorViews[1] },
      },
      history: [],
      scrollKey: null,
      cellLogs: [],
    });
    const result = getCodes(otherCode);
    expect(result).toEqual("import os\nx = 1\nprint('Hello World')");
  });

  it("should sort import statements at the top", () => {
    const otherCode = "print('Hello World')";
    const mockEditorViews = [
      createMockEditorView("x = 1"),
      createMockEditorView("import os"),
    ];
    store.set(notebookAtom, {
      cellIds: MultiColumn.from([[Cells.cell1, Cells.cell2]]),
      cellData: {},
      cellRuntime: {},
      cellHandles: {
        [Cells.cell1]: { current: mockEditorViews[0] },
        [Cells.cell2]: { current: mockEditorViews[1] },
      },
      history: [],
      scrollKey: null,
      cellLogs: [],
    });
    const result = getCodes(otherCode);
    expect(result).toEqual("import os\nx = 1\nprint('Hello World')");
  });

  it("should return topologically sorted codes", () => {
    const otherCode = "print('Hello World')";
    const mockEditorViews = [
      createMockEditorView("import os"),
      createMockEditorView("x = 1"),
      createMockEditorView("y = x + 1"),
    ];
    store.set(notebookAtom, {
      cellIds: MultiColumn.from([[Cells.cell1, Cells.cell2, Cells.cell3]]),
      cellData: {},
      cellRuntime: {},
      cellHandles: {
        [Cells.cell1]: { current: mockEditorViews[0] },
        [Cells.cell2]: { current: mockEditorViews[1] },
        [Cells.cell3]: { current: mockEditorViews[2] },
      },
      history: [],
      scrollKey: null,
      cellLogs: [],
    });
    store.set(variablesAtom, {
      [Variables.var1]: {
        name: Variables.var1,
        declaredBy: [Cells.cell1],
        usedBy: [Cells.cell2, Cells.cell3],
      },
    });
    const result = getCodes(otherCode);
    expect(result).toEqual("import os\nx = 1\ny = x + 1\nprint('Hello World')");
  });
});
