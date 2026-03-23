/* Copyright 2026 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */

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

      expect(items).toHaveLength(1);
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
      expect(items[0].data.errors[0].cellName).toBe("");
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
          "apply": "@Errors",
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
      expect(context).toMatchSnapshot("basic-error-context");
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

      // Check for expected content instead of exact snapshot match due to random cell IDs
      expect(context).toMatchInlineSnapshot(`
        "<error name="Cell 1" description="Invalid syntax
        Runtime error"></error>

        <error name="Cell cell-2" description="This cell is in a cycle
        The variable 'variable_x' was defined by another cell"></error>"
      `);
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
      const context = provider.formatContext(items[0]);
      expect(context).toContain(`Cell ${cellId}`);
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
        expect(items).toHaveLength(1);
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
