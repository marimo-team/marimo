/* Copyright 2026 Marimo. All rights reserved. */
/* oxlint-disable typescript/no-explicit-any */

import type * as Protocol from "@marimo-team/client/protocol";
import { createStore } from "jotai";
import { beforeEach, describe, expect, it } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { notebookAtom } from "@/core/cells/cells";
import { type CellId, CellId as CellIdClass } from "@/core/cells/ids";
import { ErrorContextProvider } from "../error";

const SYNTAX: Partial<Protocol.Error> = {
  kind: "invalid-syntax",
  message: "Invalid syntax",
};
const RUNTIME: Partial<Protocol.Error> = {
  kind: "exception",
  name: "RuntimeError",
  message: "Runtime error",
};

describe("ErrorContextProvider", () => {
  let provider: ErrorContextProvider;
  let store: ReturnType<typeof createStore>;

  beforeEach(() => {
    store = createStore();
    provider = new ErrorContextProvider(store);
  });

  const createMockNotebookWithErrors = (
    errors: Parameters<typeof MockNotebook.withErrors>[1],
  ) => MockNotebook.withErrors(store, errors);

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
        { cellId: cellId1, cellName: "Cell 1", error: SYNTAX },
        { cellId: cellId2, cellName: "Cell 2", error: RUNTIME },
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

      createMockNotebookWithErrors([{ cellId, cellName: "", error: SYNTAX }]);

      const items = provider.getItems();
      expect(items[1].data).toMatchObject({
        type: "cell-error",
        error: { cellName: "cell-0" },
      });
      expect(items[1].name).toBe("Error: cell-0");
      expect(items[1].description).toBe("Invalid syntax");
    });
  });

  describe("formatCompletion", () => {
    it("should format completion for all-errors type", () => {
      const cellId1 = CellIdClass.create();
      const cellId2 = CellIdClass.create();

      createMockNotebookWithErrors([
        { cellId: cellId1, cellName: "Cell 1", error: SYNTAX },
        { cellId: cellId2, cellName: "Cell 2", error: RUNTIME },
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
      if (typeof completion.info !== "function") {
        throw new Error("Expected completion info to be a function");
      }
      const infoResult = completion.info(completion);
      if (!infoResult || typeof infoResult !== "object") {
        throw new Error("Expected completion info to return an element");
      }
      const infoElement = (
        "dom" in infoResult ? infoResult.dom : infoResult
      ) as HTMLElement;
      expect(infoElement.tagName).toBe("DIV");
      expect(infoElement.textContent).toContain("Errors");
      expect(infoElement.textContent).toContain("2 errors");
    });

    it("should handle single error correctly", () => {
      const cellId = CellIdClass.create();

      createMockNotebookWithErrors([
        { cellId, cellName: "Cell 1", error: SYNTAX },
      ]);

      const items = provider.getItems();
      const completion = provider.formatCompletion(items[0]);
      expect(completion.detail).toBe("1 error");
    });

    it("formats completion for a single cell error", () => {
      const cellId = CellIdClass.create();

      createMockNotebookWithErrors([
        { cellId, cellName: "Cell 1", error: SYNTAX },
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
        { cellId, cellName: "Cell 1", error: SYNTAX },
      ]);

      const items = provider.getItems();
      const context = provider.formatContext(items[0]);
      expect(context).toContain("Invalid syntax");
      expect(context).toContain("Code:");
    });

    it("should format context for several kinds of error", () => {
      const cellId1 = "cell-1" as CellId;
      const cellId2 = "cell-2" as CellId;

      createMockNotebookWithErrors([
        { cellId: cellId1, cellName: "Cell 1", error: SYNTAX },
        {
          cellId: cellId2,
          cellName: "",
          error: {
            kind: "cycle-dependencies",
            message: "This cell is in a cycle",
          },
        },
      ]);

      const items = provider.getItems();
      const context = provider.formatContext(items[0]);

      expect(context).toContain("Invalid syntax");
      expect(context).toContain("This cell is in a cycle");
    });

    it("should handle cells without names", () => {
      const cellId = CellIdClass.create();

      createMockNotebookWithErrors([{ cellId, cellName: "", error: SYNTAX }]);

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
          error: {
            kind: "exception",
            name: "ValueError",
            message: "boom",
            traceback: {
              mimetype: "text/html",
              data: "<pre>line 1\nline 2</pre>",
            },
          },
        },
      ]);

      const items = provider.getItems();
      const context = provider.formatContext(items[1]);
      expect(context).toContain("boom");
      expect(context).toContain("line 1");
      expect(context).toContain("line 2");
    });

    it("includes console tracebacks for marimo error outputs", () => {
      const cellId = CellIdClass.create();
      const notebookState = createMockNotebookWithErrors([
        {
          cellId,
          cellName: "Cell 1",
          code: "raise ValueError('boom')",
          error: { kind: "exception", name: "ValueError", message: "boom" },
        },
      ]);
      notebookState.cellRuntime[cellId] = {
        ...notebookState.cellRuntime[cellId],
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
      const notebookState = createMockNotebookWithErrors([
        {
          cellId,
          cellName: "Cell 1",
          code: "raise ValueError('boom')",
          error: {
            kind: "exception",
            name: "ValueError",
            message: "boom",
            traceback: {
              mimetype: "text/html",
              data: "<pre>embedded line 1</pre>",
            },
          },
        },
      ]);
      notebookState.cellRuntime[cellId] = {
        ...notebookState.cellRuntime[cellId],
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
    it("describes each kind of host error", () => {
      const errors: { error: Partial<Protocol.Error>; expected: string }[] = [
        {
          error: { kind: "exception", message: "Runtime exception" },
          expected: "Runtime exception",
        },
        {
          error: { kind: "invalid-syntax", message: "Syntax error" },
          expected: "Syntax error",
        },
        {
          error: { kind: "interrupted", message: "" },
          expected: "This cell was interrupted and needs to be re-run",
        },
        {
          error: { kind: "internal", message: "Unknown error" },
          expected: "Unknown error",
        },
        {
          // Any other kind is a diagnostic, shown as the host wrote it.
          error: {
            kind: "multiple-definitions",
            message: "x is defined twice",
          },
          expected: "x is defined twice",
        },
      ];

      for (const { error, expected } of errors) {
        // Create a fresh store and provider for each error type
        const testStore = createStore();
        const testProvider = new ErrorContextProvider(testStore);
        MockNotebook.withErrors(testStore, [
          { cellId: CellIdClass.create(), cellName: "Cell 1", error },
        ]);

        const items = testProvider.getItems();
        // One "all-errors" item plus one per-cell error item.
        expect(items).toHaveLength(2);
        const context = testProvider.formatContext(items[0]);
        expect(context).toContain(expected);
      }
    });
  });
});
