/* Copyright 2026 Marimo. All rights reserved. */
/* oxlint-disable typescript/no-explicit-any */

import { createStore } from "jotai";
import { beforeEach, describe, expect, it } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { notebookAtom } from "@/core/cells/cells";
import { type CellId, CellId as CellIdClass } from "@/core/cells/ids";
import { ErrorContextProvider } from "../error";

describe("ErrorContextProvider", () => {
  let provider: ErrorContextProvider;
  let store: ReturnType<typeof createStore>;

  beforeEach(() => {
    store = createStore();
    provider = new ErrorContextProvider(store);
  });

  const createMockNotebookWithErrors = (
    errors: Parameters<typeof MockNotebook.notebookStateWithErrors>[0],
  ) => {
    const notebookState = MockNotebook.notebookStateWithErrors(errors);
    store.set(notebookAtom, notebookState);
  };

  describe("provider properties", () => {
    it("should have correct provider properties", () => {
      expect(provider.title).toBe("Errors");
      expect(provider.mentionPrefix).toBe("@");
      expect(provider.contextType).toBe("error");
    });
  });

  describe("getItems", () => {
    it("should return empty array when no errors", () => {
      const items = provider.getItems();
      expect(items).toEqual([]);
    });

    it("should return error items when errors exist", () => {
      const cellId1 = CellIdClass.create();
      const cellId2 = CellIdClass.create();

      createMockNotebookWithErrors([
        {
          cellId: cellId1,
          cellName: "Cell 1",
          errorData: [MockNotebook.errors.syntax("Invalid syntax")],
        },
        {
          cellId: cellId2,
          cellName: "Cell 2",
          errorData: [MockNotebook.errors.exception("Runtime error")],
        },
      ]);

      const items = provider.getItems();

      expect(items).toHaveLength(3);
      expect(items[0]).toMatchObject({
        name: "Errors",
        type: "error",
        description: "All errors in the notebook",
        data: {
          type: "all-errors",
          errors: [
            {
              cellId: cellId1,
              cellName: "Cell 1",
              errorData: [{ type: "syntax", msg: "Invalid syntax" }],
            },
            {
              cellId: cellId2,
              cellName: "Cell 2",
              errorData: [{ type: "exception", msg: "Runtime error" }],
            },
          ],
        },
      });
      expect(items[1]).toMatchObject({
        uri: `error://${cellId1}`,
        name: "Error: Cell 1",
        description: "Invalid syntax",
        data: { type: "cell-error", error: { cellId: cellId1 } },
      });
      expect(items[2]).toMatchObject({
        uri: `error://${cellId2}`,
        name: "Error: Cell 2",
        description: "Runtime error",
        data: { type: "cell-error", error: { cellId: cellId2 } },
      });
    });

    it("should handle cells without names", () => {
      const cellId = CellIdClass.create();

      createMockNotebookWithErrors([
        {
          cellId,
          cellName: "",
          errorData: [MockNotebook.errors.syntax("Invalid syntax")],
        },
      ]);

      const items = provider.getItems();
      expect(items[1].data.type).toBe("cell-error");
      if (items[1].data.type === "cell-error") {
        expect(items[1].data.error.cellName).toBe("cell-0");
      }
      expect(items[1].name).toBe("Error: cell-0");
      expect(items[1].description).toBe("Invalid syntax");
    });
  });

  describe("formatCompletion", () => {
    it("should format completion for all-errors type", () => {
      const cellId1 = CellIdClass.create();
      const cellId2 = CellIdClass.create();

      createMockNotebookWithErrors([
        {
          cellId: cellId1,
          cellName: "Cell 1",
          errorData: [MockNotebook.errors.syntax("Invalid syntax")],
        },
        {
          cellId: cellId2,
          cellName: "Cell 2",
          errorData: [MockNotebook.errors.exception("Runtime error")],
        },
      ]);

      const items = provider.getItems();
      const completion = provider.formatCompletion(items[0]);

      expect(completion).toMatchInlineSnapshot(`
        {
          "apply": "@error://all",
          "detail": "2 errors",
          "displayLabel": "Errors",
          "info": [Function],
          "label": "@Errors",
          "section": {
            "name": "Error",
            "rank": 1,
          },
          "type": "error",
        }
      `);

      // Test the info function
      expect(completion.info).toBeDefined();
      if (typeof completion.info === "function") {
        const infoResult = completion.info(completion);
        if (
          infoResult &&
          typeof infoResult === "object" &&
          "dom" in infoResult
        ) {
          const infoElement = infoResult.dom as HTMLElement;
          expect(infoElement.tagName).toBe("DIV");
          expect(infoElement.textContent).toContain("Errors");
          expect(infoElement.textContent).toContain("2 errors");
        } else if (infoResult && "tagName" in (infoResult as any)) {
          const infoElement = infoResult as HTMLElement;
          expect(infoElement.tagName).toBe("DIV");
          expect(infoElement.textContent).toContain("Errors");
          expect(infoElement.textContent).toContain("2 errors");
        }
      }
    });

    it("should handle single error correctly", () => {
      const cellId = CellIdClass.create();

      createMockNotebookWithErrors([
        {
          cellId,
          cellName: "Cell 1",
          errorData: [MockNotebook.errors.syntax("Invalid syntax")],
        },
      ]);

      const items = provider.getItems();
      const completion = provider.formatCompletion(items[0]);
      expect(completion.detail).toBe("1 error");
    });

    it("formats completion for a single cell error", () => {
      const cellId = CellIdClass.create();

      createMockNotebookWithErrors([
        {
          cellId,
          cellName: "Cell 1",
          errorData: [MockNotebook.errors.syntax("Invalid syntax")],
        },
      ]);

      const items = provider.getItems();
      const completion = provider.formatCompletion(items[1]);
      expect(completion.apply).toBe(`@error://${cellId}`);
      expect(completion.displayLabel).toBe("Error: Cell 1");
      expect(items[1].name).toBe("Error: Cell 1");
    });

    it("should handle fallback for unknown error types", () => {
      const item = {
        uri: "error://unknown",
        name: "Unknown Error",
        type: "error" as const,
        data: {
          type: "unknown" as any,
          errors: [],
        },
        description: "Unknown error type",
      };

      const completion = provider.formatCompletion(item);
      expect(completion).toMatchInlineSnapshot(`
        {
          "displayLabel": "Error",
          "label": "Error",
          "section": {
            "name": "Error",
            "rank": 1,
          },
        }
      `);
    });
  });

  describe("formatContext", () => {
    it("should format context for basic errors", () => {
      const cellId = CellIdClass.create();

      createMockNotebookWithErrors([
        {
          cellId,
          cellName: "Cell 1",
          errorData: [MockNotebook.errors.syntax("Invalid syntax")],
        },
      ]);

      const items = provider.getItems();
      const context = provider.formatContext(items[0]);
      expect(context).toContain("Invalid syntax");
      expect(context).toContain("Code:");
    });

    it("should format context for multiple error types", () => {
      const cellId1 = "cell-1" as CellId;
      const cellId2 = "cell-2" as CellId;

      createMockNotebookWithErrors([
        {
          cellId: cellId1,
          cellName: "Cell 1",
          errorData: [
            MockNotebook.errors.syntax("Invalid syntax"),
            MockNotebook.errors.exception("Runtime error"),
          ],
        },
        {
          cellId: cellId2,
          cellName: "",
          errorData: [
            MockNotebook.errors.cycle(),
            MockNotebook.errors.multipleDefs("variable_x"),
          ],
        },
      ]);

      const items = provider.getItems();
      const context = provider.formatContext(items[0]);

      expect(context).toContain("Invalid syntax");
      expect(context).toContain("Runtime error");
      expect(context).toContain("This cell is in a cycle");
      expect(context).toContain(
        "The variable 'variable_x' was defined by another cell",
      );
    });

    it("should handle cells without names", () => {
      const cellId = CellIdClass.create();

      createMockNotebookWithErrors([
        {
          cellId,
          cellName: "",
          errorData: [MockNotebook.errors.syntax("Invalid syntax")],
        },
      ]);

      const items = provider.getItems();
      const context = provider.formatContext(items[1]);
      expect(context).toContain(`cellId="${cellId}"`);
      expect(context).toContain("Invalid syntax");
    });

    it("includes exception tracebacks in formatted context", () => {
      const cellId = CellIdClass.create();

      createMockNotebookWithErrors([
        {
          cellId,
          cellName: "Cell 1",
          errorData: [
            {
              type: "exception",
              msg: "boom",
              exception_type: "ValueError",
              raising_cell: null,
              traceback: "<pre>line 1\nline 2</pre>",
            },
          ],
        },
      ]);

      const items = provider.getItems();
      const context = provider.formatContext(items[1]);
      expect(context).toContain("boom");
      expect(context).toContain("line 1");
      expect(context).toContain("line 2");
    });

    it("includes traceback-only cell outputs", () => {
      const cellId = CellIdClass.create();
      const notebookState = MockNotebook.notebookState({
        cellData: {
          [cellId]: {
            name: "Cell 1",
            code: "raise ValueError('boom')",
          },
        },
      });
      notebookState.cellRuntime[cellId] = {
        ...notebookState.cellRuntime[cellId],
        output: {
          channel: "marimo-error",
          data: "<pre>ValueError: boom\n  line 1</pre>",
          mimetype: "application/vnd.marimo+traceback",
          timestamp: Date.now(),
        },
      };
      store.set(notebookAtom, notebookState);

      const items = provider.getItems();
      expect(items).toHaveLength(2);
      expect(items[1].description).toBe("ValueError: boom");
      const context = provider.formatContext(items[1]);
      expect(context).toContain("raise ValueError('boom')");
      expect(context).toContain("ValueError: boom");
      expect(context).toContain("line 1");
    });

    it("includes console tracebacks for marimo error outputs", () => {
      const cellId = CellIdClass.create();
      const notebookState = MockNotebook.notebookState({
        cellData: {
          [cellId]: {
            name: "Cell 1",
            code: "raise ValueError('boom')",
          },
        },
      });
      notebookState.cellRuntime[cellId] = {
        ...notebookState.cellRuntime[cellId],
        output: {
          channel: "marimo-error",
          data: [
            {
              type: "exception",
              msg: "boom",
              exception_type: "ValueError",
              raising_cell: null,
            },
          ],
          mimetype: "application/vnd.marimo+error",
          timestamp: Date.now(),
        },
        consoleOutputs: [
          {
            channel: "stderr",
            data: '<pre>ValueError: boom\n  File "notebook.py", line 1</pre>',
            mimetype: "application/vnd.marimo+traceback",
            timestamp: Date.now(),
          },
        ],
      };
      store.set(notebookAtom, notebookState);

      const items = provider.getItems();
      const context = provider.formatContext(items[1]);
      expect(context).toContain("boom");
      expect(context).toContain("ValueError: boom");
      expect(context).toContain('File "notebook.py", line 1');
      expect(items[1].description).toBe("boom");
    });

    it("does not duplicate console traceback when error already has one", () => {
      const cellId = CellIdClass.create();
      const notebookState = MockNotebook.notebookState({
        cellData: {
          [cellId]: {
            name: "Cell 1",
            code: "raise ValueError('boom')",
          },
        },
      });
      notebookState.cellRuntime[cellId] = {
        ...notebookState.cellRuntime[cellId],
        output: {
          channel: "marimo-error",
          data: [
            {
              type: "exception",
              msg: "boom",
              exception_type: "ValueError",
              raising_cell: null,
              traceback: "<pre>embedded line 1</pre>",
            },
          ],
          mimetype: "application/vnd.marimo+error",
          timestamp: Date.now(),
        },
        consoleOutputs: [
          {
            channel: "stderr",
            data: "<pre>console line 1</pre>",
            mimetype: "application/vnd.marimo+traceback",
            timestamp: Date.now(),
          },
        ],
      };
      store.set(notebookAtom, notebookState);

      const items = provider.getItems();
      if (items[1].data.type !== "cell-error") {
        throw new Error("Expected cell-error item");
      }
      expect(items[1].data.error.tracebackHtml).toBeUndefined();

      const context = provider.formatContext(items[1]);
      expect(context).toContain("embedded line 1");
      expect(context).not.toContain("console line 1");
      expect(items[1].description).toBe("boom");
    });
  });

  describe("error description handling", () => {
    it("should handle all error types correctly", () => {
      // Note: ancestor-* error types are intentionally filtered out by cellErrorsAtom
      const errorTypes = [
        {
          error: MockNotebook.errors.setupRefs(),
          expected: "The setup cell cannot have references",
        },
        {
          error: MockNotebook.errors.cycle(),
          expected: "This cell is in a cycle",
        },
        {
          error: MockNotebook.errors.multipleDefs("var_x"),
          expected: "The variable 'var_x' was defined by another cell",
        },
        {
          error: MockNotebook.errors.importStar("Import star error"),
          expected: "Import star error",
        },
        {
          error: MockNotebook.errors.exception("Runtime exception"),
          expected: "Runtime exception",
        },
        {
          error: MockNotebook.errors.strictException("Strict exception", "ref"),
          expected: "Strict exception",
        },
        {
          error: MockNotebook.errors.interruption(),
          expected: "This cell was interrupted and needs to be re-run",
        },
        {
          error: MockNotebook.errors.syntax("Syntax error"),
          expected: "Syntax error",
        },
        {
          error: MockNotebook.errors.unknown("Unknown error"),
          expected: "Unknown error",
        },
      ];

      for (const { error, expected } of errorTypes) {
        // Create a fresh store and provider for each error type
        const testStore = createStore();
        const testProvider = new ErrorContextProvider(testStore);

        const { notebookState } = MockNotebook.cellWithErrors("Cell 1", [
          error,
        ]);
        testStore.set(notebookAtom, notebookState);

        const items = testProvider.getItems();
        expect(items.length).toBeGreaterThanOrEqual(1);
        const context = testProvider.formatContext(items[0]);
        expect(context).toContain(expected);
      }
    });

    it("should handle unknown error type gracefully", () => {
      const error = { type: "unknown-type" as any };
      const { notebookState } = MockNotebook.cellWithErrors("Cell 1", [error]);
      store.set(notebookAtom, notebookState);

      const items = provider.getItems();
      const context = provider.formatContext(items[0]);
      expect(context).toContain("Unknown error");
    });
  });
});
