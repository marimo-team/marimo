/* Copyright 2024 Marimo. All rights reserved. */

import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { getDefaultStore } from "jotai";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import type { CellColumnId } from "@/utils/id-tree";
import { MultiColumn } from "@/utils/id-tree";
import { cellConfigExtension } from "../../../codemirror/config/extension";
import { adaptiveLanguageConfiguration } from "../../../codemirror/language/extension";
import { stagedAICellsAtom } from "../../staged-cells";
import { ToolExecutionError } from "../base";
import { EditNotebookTool } from "../edit-notebook-tool";

// Mock scrollAndHighlightCell
vi.mock("@/components/editor/links/cell-link", () => ({
  scrollAndHighlightCell: vi.fn(),
}));

// Mock updateEditorCodeFromPython
vi.mock("@/core/codemirror/language/utils", () => ({
  updateEditorCodeFromPython: vi.fn(),
}));

import { updateEditorCodeFromPython } from "@/core/codemirror/language/utils";

function createMockEditorView(code: string): EditorView {
  return new EditorView({
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
}

describe("EditNotebookTool", () => {
  let store: ReturnType<typeof getDefaultStore>;
  let tool: EditNotebookTool;
  let cellId1: CellId;
  let cellId2: CellId;
  let cellId3: CellId;

  beforeEach(() => {
    store = getDefaultStore();
    tool = new EditNotebookTool(store);

    cellId1 = "cell-1" as CellId;
    cellId2 = "cell-2" as CellId;
    cellId3 = "cell-3" as CellId;

    // Reset mocks
    vi.clearAllMocks();

    // Reset atom states
    store.set(stagedAICellsAtom, new Map());
  });

  describe("tool metadata", () => {
    it("should have correct metadata", () => {
      expect(tool.name).toBe("edit_notebook_tool");
      expect(tool.description).toBeDefined();
      expect(tool.description.baseDescription).toContain("editing operations");
      expect(tool.schema).toBeDefined();
      expect(tool.outputSchema).toBeDefined();
      expect(tool.mode).toEqual(["agent"]);
    });
  });

  describe("update_cell operation", () => {
    it("should update cell with new code", async () => {
      const oldCode = "x = 1";
      const newCode = "x = 2";

      // Create notebook state with mock editor view
      const editorView = createMockEditorView(oldCode);
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: oldCode },
        },
      });
      notebook.cellHandles[cellId1] = { current: { editorView } } as never;
      store.set(notebookAtom, notebook);

      const result = await tool.handler({
        edit: {
          type: "update_cell",
          cellId: cellId1,
          code: newCode,
        },
      });

      expect(result.status).toBe("success");
      expect(vi.mocked(updateEditorCodeFromPython)).toHaveBeenCalledWith(
        editorView,
        newCode,
      );

      // Check that cell was staged
      const stagedCells = store.get(stagedAICellsAtom);
      expect(stagedCells.has(cellId1)).toBe(true);
      expect(stagedCells.get(cellId1)).toEqual({
        type: "update_cell",
        previousCode: oldCode,
      });
    });

    it("should throw error when cell ID doesn't exist", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: "x = 1" },
        },
      });
      store.set(notebookAtom, notebook);

      await expect(
        tool.handler({
          edit: {
            type: "update_cell",
            cellId: "nonexistent" as CellId,
            code: "x = 2",
          },
        }),
      ).rejects.toThrow(ToolExecutionError);

      await expect(
        tool.handler({
          edit: {
            type: "update_cell",
            cellId: "nonexistent" as CellId,
            code: "x = 2",
          },
        }),
      ).rejects.toThrow("Cell not found");
    });

    it("should throw error when cell editor not found", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: "x = 1" },
        },
      });
      // Don't set editorView
      notebook.cellHandles[cellId1] = { current: null } as never;
      store.set(notebookAtom, notebook);

      await expect(
        tool.handler({
          edit: {
            type: "update_cell",
            cellId: cellId1,
            code: "x = 2",
          },
        }),
      ).rejects.toThrow("Cell editor not found");
    });
  });

  describe("add_cell operation", () => {
    it("should add cell at the end of the notebook", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: "x = 1" },
        },
      });
      store.set(notebookAtom, notebook);

      const newCode = "y = 2";
      const result = await tool.handler({
        edit: {
          type: "add_cell",
          position: "__end__",
          code: newCode,
        },
      });

      expect(result.status).toBe("success");

      // Check that a new cell was staged
      const stagedCells = store.get(stagedAICellsAtom);
      expect(stagedCells.size).toBe(1);
      const [cellId, edit] = [...stagedCells.entries()][0];
      expect(edit).toEqual({ type: "add_cell" });
      expect(cellId).toBeDefined();
    });

    it("should add cell before a specific cell", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: "x = 1" },
          [cellId2]: { code: "x = 2" },
        },
      });
      store.set(notebookAtom, notebook);

      const newCode = "y = 2";
      const result = await tool.handler({
        edit: {
          type: "add_cell",
          position: { cellId: cellId2, before: true },
          code: newCode,
        },
      });

      expect(result.status).toBe("success");

      // Check that a new cell was staged
      const stagedCells = store.get(stagedAICellsAtom);
      expect(stagedCells.size).toBe(1);
      const [_cellId, edit] = [...stagedCells.entries()][0];
      expect(edit).toEqual({ type: "add_cell" });
    });

    it("should add cell after a specific cell", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: "x = 1" },
          [cellId2]: { code: "x = 2" },
        },
      });
      store.set(notebookAtom, notebook);

      const newCode = "y = 2";
      const result = await tool.handler({
        edit: {
          type: "add_cell",
          position: { cellId: cellId2, before: false },
          code: newCode,
        },
      });

      expect(result.status).toBe("success");

      // Check that a new cell was staged
      const stagedCells = store.get(stagedAICellsAtom);
      expect(stagedCells.size).toBe(1);
    });

    it("should add cell at the end of a specific column", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: "x = 1" },
          [cellId2]: { code: "x = 2" },
        },
      });
      // Create multi-column layout
      notebook.cellIds = MultiColumn.from([[cellId1], [cellId2]]);
      const columnId = notebook.cellIds.getColumns()[1].id;
      store.set(notebookAtom, notebook);

      const newCode = "y = 2";
      const result = await tool.handler({
        edit: {
          type: "add_cell",
          position: { type: "__end__", columnId },
          code: newCode,
        },
      });

      expect(result.status).toBe("success");

      // Check that a new cell was staged
      const stagedCells = store.get(stagedAICellsAtom);
      expect(stagedCells.size).toBe(1);
    });

    it("should throw error when cell ID doesn't exist for position", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: "x = 1" },
        },
      });
      store.set(notebookAtom, notebook);

      await expect(
        tool.handler({
          edit: {
            type: "add_cell",
            position: { cellId: "nonexistent" as CellId, before: true },
            code: "y = 2",
          },
        }),
      ).rejects.toThrow("Cell not found");
    });

    it("should throw error when column ID doesn't exist", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: "x = 1" },
        },
      });
      store.set(notebookAtom, notebook);

      await expect(
        tool.handler({
          edit: {
            type: "add_cell",
            position: {
              type: "__end__",
              columnId: "nonexistent" as CellColumnId,
            },
            code: "y = 2",
          },
        }),
      ).rejects.toThrow("Column not found");
    });
  });

  describe("delete_cell operation", () => {
    it("should delete a cell", async () => {
      const cellCode = "x = 1";
      const editorView = createMockEditorView(cellCode);
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: cellCode },
          [cellId2]: { code: "x = 2" },
        },
      });
      notebook.cellHandles[cellId1] = { current: { editorView } } as never;
      store.set(notebookAtom, notebook);

      const result = await tool.handler({
        edit: {
          type: "delete_cell",
          cellId: cellId1,
        },
      });

      expect(result.status).toBe("success");

      // Check that cell was staged for deletion
      const stagedCells = store.get(stagedAICellsAtom);
      expect(stagedCells.has(cellId1)).toBe(true);
      expect(stagedCells.get(cellId1)).toEqual({
        type: "delete_cell",
        previousCode: cellCode,
      });
    });

    it("should throw error when cell ID doesn't exist", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: "x = 1" },
        },
      });
      store.set(notebookAtom, notebook);

      await expect(
        tool.handler({
          edit: {
            type: "delete_cell",
            cellId: "nonexistent" as CellId,
          },
        }),
      ).rejects.toThrow("Cell not found");
    });

    it("should throw error when cell editor not found", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: "x = 1" },
        },
      });
      // Don't set editorView
      notebook.cellHandles[cellId1] = { current: null } as never;
      store.set(notebookAtom, notebook);

      await expect(
        tool.handler({
          edit: {
            type: "delete_cell",
            cellId: cellId1,
          },
        }),
      ).rejects.toThrow("Cell editor not found");
    });
  });

  describe("validation", () => {
    it("should validate cell exists in multi-column notebook", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: "x = 1" },
          [cellId2]: { code: "x = 2" },
          [cellId3]: { code: "x = 3" },
        },
      });
      // Create multi-column layout
      notebook.cellIds = MultiColumn.from([[cellId1, cellId2], [cellId3]]);
      store.set(notebookAtom, notebook);

      // Should not throw for cells in different columns
      const editorView = createMockEditorView("x = 1");
      notebook.cellHandles[cellId1] = { current: { editorView } } as never;
      notebook.cellHandles[cellId3] = { current: { editorView } } as never;

      await expect(
        tool.handler({
          edit: {
            type: "update_cell",
            cellId: cellId1,
            code: "y = 1",
          },
        }),
      ).resolves.toBeDefined();

      await expect(
        tool.handler({
          edit: {
            type: "update_cell",
            cellId: cellId3,
            code: "y = 3",
          },
        }),
      ).resolves.toBeDefined();
    });
  });

  describe("return value", () => {
    it("should return success status with next steps", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: "x = 1" },
        },
      });
      store.set(notebookAtom, notebook);

      const result = await tool.handler({
        edit: {
          type: "add_cell",
          position: "__end__",
          code: "y = 2",
        },
      });

      expect(result.status).toBe("success");
      expect(result.next_steps).toBeDefined();
      expect(Array.isArray(result.next_steps)).toBe(true);
      expect(result.next_steps?.length).toBeGreaterThan(0);
    });
  });

  describe("schema validation", () => {
    it("should validate update_cell input", () => {
      const validInput = {
        edit: {
          type: "update_cell",
          cellId: cellId1,
          code: "x = 2",
        },
      };

      const result = tool.schema.safeParse(validInput);
      expect(result.success).toBe(true);
    });

    it("should validate add_cell input with __end__ position", () => {
      const validInput = {
        edit: {
          type: "add_cell",
          position: "__end__",
          code: "x = 2",
        },
      };

      const result = tool.schema.safeParse(validInput);
      expect(result.success).toBe(true);
    });

    it("should validate add_cell input with cellId position", () => {
      const validInput = {
        edit: {
          type: "add_cell",
          position: {
            cellId: cellId1,
            before: true,
          },
          code: "x = 2",
        },
      };

      const result = tool.schema.safeParse(validInput);
      expect(result.success).toBe(true);
    });

    it("should validate add_cell input with columnId position", () => {
      const validInput = {
        edit: {
          type: "add_cell",
          position: {
            type: "__end__",
            columnId: "column-1" as CellColumnId,
          },
          code: "x = 2",
        },
      };

      const result = tool.schema.safeParse(validInput);
      expect(result.success).toBe(true);
    });

    it("should validate delete_cell input", () => {
      const validInput = {
        edit: {
          type: "delete_cell",
          cellId: cellId1,
        },
      };

      const result = tool.schema.safeParse(validInput);
      expect(result.success).toBe(true);
    });

    it("should reject invalid input", () => {
      const invalidInput = {
        edit: {
          type: "invalid_type",
        },
      };

      const result = tool.schema.safeParse(invalidInput);
      expect(result.success).toBe(false);
    });
  });
});
