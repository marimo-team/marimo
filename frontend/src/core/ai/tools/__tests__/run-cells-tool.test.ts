/* Copyright 2026 Marimo. All rights reserved. */

import { getDefaultStore } from "jotai";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import { notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { RunStaleCellsTool } from "../run-cells-tool";

// Mock runCells
vi.mock("@/components/editor/cell/useRunCells", () => ({
  runCells: vi.fn(),
}));

// Mock getCellContextData
vi.mock("../../context/providers/cell-output", () => ({
  getCellContextData: vi.fn(),
}));

import { runCells } from "@/components/editor/cell/useRunCells";
import { getCellContextData } from "../../context/providers/cell-output";

describe("RunStaleCellsTool", () => {
  let store: ReturnType<typeof getDefaultStore>;
  let tool: RunStaleCellsTool;
  let cellId1: CellId;
  let cellId2: CellId;
  let cellId3: CellId;
  let toolContext: {
    addStagedCell: ReturnType<typeof vi.fn>;
    createNewCell: ReturnType<typeof vi.fn>;
    prepareForRun: ReturnType<typeof vi.fn>;
    sendRun: ReturnType<typeof vi.fn>;
    store: ReturnType<typeof getDefaultStore>;
  };

  beforeEach(() => {
    store = getDefaultStore();
    toolContext = {
      addStagedCell: vi.fn(),
      createNewCell: vi.fn(),
      prepareForRun: vi.fn(),
      sendRun: vi.fn().mockResolvedValue(null),
      store,
    };

    tool = new RunStaleCellsTool({ postExecutionDelay: 0 });

    cellId1 = cellId("cell-1");
    cellId2 = cellId("cell-2");
    cellId3 = cellId("cell-3");

    // Reset mocks
    vi.clearAllMocks();
  });

  describe("no stale cells", () => {
    it("should return success message when no stale cells exist", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: {
            code: "x = 1",
            edited: false,
            lastCodeRun: "x = 1",
            lastExecutionTime: 100,
          },
        },
      });
      // Make sure cell is not stale by setting runtime state
      notebook.cellRuntime[cellId1] = {
        ...notebook.cellRuntime[cellId1],
        runElapsedTimeMs: 100 as never,
        status: "idle",
      };
      store.set(notebookAtom, notebook);

      const result = await tool.handler({}, toolContext as never);

      expect(result.status).toBe("success");
      expect(result.message).toBe("No stale cells found.");
      expect(result.cellsToOutput).toBeUndefined();
      expect(vi.mocked(runCells)).not.toHaveBeenCalled();
    });
  });

  describe("running stale cells", () => {
    it("should run stale cells and return their outputs", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: {
            code: "x = 1",
            edited: true,
            lastCodeRun: null,
          },
          [cellId2]: {
            code: "y = 2",
            edited: false,
            lastCodeRun: "y = 2",
            lastExecutionTime: 100,
          },
          [cellId3]: {
            code: "z = 3",
            edited: true,
            lastCodeRun: "z = 2",
          },
        },
      });
      // Make cellId2 not stale
      notebook.cellRuntime[cellId2] = {
        ...notebook.cellRuntime[cellId2],
        runElapsedTimeMs: 100 as never,
        status: "idle",
      };
      store.set(notebookAtom, notebook);

      // Mock runCells to update cell runtime status
      vi.mocked(runCells).mockImplementation(async () => {
        const updatedNotebook = store.get(notebookAtom);
        updatedNotebook.cellRuntime[cellId1] = {
          ...updatedNotebook.cellRuntime[cellId1],
          status: "idle",
        };
        updatedNotebook.cellRuntime[cellId3] = {
          ...updatedNotebook.cellRuntime[cellId3],
          status: "idle",
        };
        store.set(notebookAtom, updatedNotebook);
      });

      // Mock getCellContextData to return outputs
      vi.mocked(getCellContextData).mockImplementation((cellId) => {
        if (cellId === cellId1) {
          return {
            cellOutput: {
              outputType: "text",
              processedContent: "1",
              imageUrl: null,
              output: {},
            },
            consoleOutputs: null,
            cellName: "cell1",
          } as never;
        }
        if (cellId === cellId3) {
          return {
            cellOutput: {
              outputType: "text",
              processedContent: "3",
              imageUrl: null,
              output: {},
            },
            consoleOutputs: null,
            cellName: "cell3",
          } as never;
        }
        return {} as never;
      });

      const result = await tool.handler({}, toolContext as never);

      expect(result.status).toBe("success");
      expect(result.cellsToOutput).toBeDefined();
      expect(result.cellsToOutput).toHaveProperty(cellId1);
      expect(result.cellsToOutput).toHaveProperty(cellId3);
      expect(result.cellsToOutput).not.toHaveProperty(cellId2);

      // Verify runCells was called with correct parameters
      expect(vi.mocked(runCells)).toHaveBeenCalledWith({
        cellIds: [cellId1, cellId3],
        sendRun: toolContext.sendRun,
        prepareForRun: toolContext.prepareForRun,
        notebook,
      });
    });

    it("should handle cells with no output", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: "x = 1", edited: true },
        },
      });
      store.set(notebookAtom, notebook);

      // Mock runCells
      vi.mocked(runCells).mockImplementation(async () => {
        const updatedNotebook = store.get(notebookAtom);
        updatedNotebook.cellRuntime[cellId1] = {
          ...updatedNotebook.cellRuntime[cellId1],
          status: "idle",
        };
        store.set(notebookAtom, updatedNotebook);
      });

      // Mock getCellContextData to return no outputs
      vi.mocked(getCellContextData).mockReturnValue({
        cellOutput: null,
        consoleOutputs: null,
        cellName: "cell1",
      } as never);

      const result = await tool.handler({}, toolContext as never);

      expect(result.status).toBe("success");
      expect(result.cellsToOutput).toBeDefined();
      expect(result.cellsToOutput?.[cellId1]).toBeNull();
    });

    it("should handle cells with console output", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: 'print("hello")', edited: true },
        },
      });
      store.set(notebookAtom, notebook);

      // Mock runCells
      vi.mocked(runCells).mockImplementation(async () => {
        const updatedNotebook = store.get(notebookAtom);
        updatedNotebook.cellRuntime[cellId1] = {
          ...updatedNotebook.cellRuntime[cellId1],
          status: "idle",
        };
        store.set(notebookAtom, updatedNotebook);
      });

      // Mock getCellContextData to return console output
      vi.mocked(getCellContextData).mockReturnValue({
        cellOutput: null,
        consoleOutputs: [
          {
            outputType: "text",
            processedContent: "hello",
            imageUrl: null,
            output: {},
          },
        ],
        cellName: "cell1",
      } as never);

      const result = await tool.handler({}, toolContext as never);

      expect(result.status).toBe("success");
      expect(result.cellsToOutput).toBeDefined();
      expect(result.cellsToOutput?.[cellId1]?.consoleOutput).toContain("hello");
      expect(result.message).toContain("Console output");
    });

    it("should handle cells with media output", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: "plt.plot()", edited: true },
        },
      });
      store.set(notebookAtom, notebook);

      // Mock runCells
      vi.mocked(runCells).mockImplementation(async () => {
        const updatedNotebook = store.get(notebookAtom);
        updatedNotebook.cellRuntime[cellId1] = {
          ...updatedNotebook.cellRuntime[cellId1],
          status: "idle",
        };
        store.set(notebookAtom, updatedNotebook);
      });

      // Mock getCellContextData to return media output
      vi.mocked(getCellContextData).mockReturnValue({
        cellOutput: {
          outputType: "media",
          processedContent: null,
          imageUrl: "https://example.com/image.png",
          output: { mimetype: "image/png" },
        },
        consoleOutputs: null,
        cellName: "cell1",
      } as never);

      const result = await tool.handler({}, toolContext as never);

      expect(result.status).toBe("success");
      expect(result.cellsToOutput).toBeDefined();
      expect(result.cellsToOutput?.[cellId1]?.cellOutput).toContain(
        "image/png",
      );
      expect(result.cellsToOutput?.[cellId1]?.cellOutput).toContain(
        "https://example.com/image.png",
      );
    });

    it("should handle both cell output and console output", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: 'x = 1; print("debug")', edited: true },
        },
      });
      store.set(notebookAtom, notebook);

      // Mock runCells
      vi.mocked(runCells).mockImplementation(async () => {
        const updatedNotebook = store.get(notebookAtom);
        updatedNotebook.cellRuntime[cellId1] = {
          ...updatedNotebook.cellRuntime[cellId1],
          status: "idle",
        };
        store.set(notebookAtom, updatedNotebook);
      });

      // Mock getCellContextData to return both outputs
      vi.mocked(getCellContextData).mockReturnValue({
        cellOutput: {
          outputType: "text",
          processedContent: "1",
          imageUrl: null,
          output: {},
        },
        consoleOutputs: [
          {
            outputType: "text",
            processedContent: "debug",
            imageUrl: null,
            output: {},
          },
        ],
        cellName: "cell1",
      } as never);

      const result = await tool.handler({}, toolContext as never);

      expect(result.status).toBe("success");
      expect(result.cellsToOutput).toBeDefined();
      expect(result.cellsToOutput?.[cellId1]?.cellOutput).toContain("1");
      expect(result.cellsToOutput?.[cellId1]?.consoleOutput).toContain("debug");
    });

    it("should handle cell output with object output", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: "x = {'a': 1, 'b': 2}", edited: true },
        },
      });
      store.set(notebookAtom, notebook);

      // Mock runCells
      vi.mocked(runCells).mockImplementation(async () => {
        const updatedNotebook = store.get(notebookAtom);
        updatedNotebook.cellRuntime[cellId1] = {
          ...updatedNotebook.cellRuntime[cellId1],
          status: "idle",
        };
        store.set(notebookAtom, updatedNotebook);
      });

      // Mock getCellContextData to return object output
      vi.mocked(getCellContextData).mockReturnValue({
        cellOutput: {
          outputType: "text",
          processedContent: null,
          imageUrl: null,
          output: { data: JSON.stringify({ a: 1, b: 2 }) },
        },
        consoleOutputs: null,
        cellName: "cell1",
      } as never);

      const result = await tool.handler({}, toolContext as never);

      expect(result.status).toBe("success");
      expect(result.cellsToOutput).toBeDefined();
      expect(result.cellsToOutput?.[cellId1]?.cellOutput).toEqual(
        'Output:\n{"a":1,"b":2}',
      );
    });

    it("should return success when all stale cells have no output", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: "x = 1", edited: true },
          [cellId2]: { code: "y = 2", edited: true },
        },
      });
      store.set(notebookAtom, notebook);

      // Mock runCells
      vi.mocked(runCells).mockImplementation(async () => {
        const updatedNotebook = store.get(notebookAtom);
        updatedNotebook.cellRuntime[cellId1] = {
          ...updatedNotebook.cellRuntime[cellId1],
          status: "idle",
        };
        updatedNotebook.cellRuntime[cellId2] = {
          ...updatedNotebook.cellRuntime[cellId2],
          status: "idle",
        };
        store.set(notebookAtom, updatedNotebook);
      });

      // Mock getCellContextData to return no outputs for both cells
      vi.mocked(getCellContextData).mockReturnValue({
        cellOutput: null,
        consoleOutputs: null,
        cellName: "cell1",
      } as never);

      const result = await tool.handler({}, toolContext as never);

      expect(result.status).toBe("success");
      expect(result.cellsToOutput).toBeDefined();
      // Both cells should be in the output as null
      expect(result.cellsToOutput?.[cellId1]).toBeNull();
      expect(result.cellsToOutput?.[cellId2]).toBeNull();
    });
  });

  describe("output truncation", () => {
    it("should summarize text/html output instead of dumping raw content", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: "fig.show()", edited: true },
        },
      });
      store.set(notebookAtom, notebook);

      vi.mocked(runCells).mockImplementation(async () => {
        const updatedNotebook = store.get(notebookAtom);
        updatedNotebook.cellRuntime[cellId1] = {
          ...updatedNotebook.cellRuntime[cellId1],
          status: "idle",
        };
        store.set(notebookAtom, updatedNotebook);
      });

      const largeHtml = `<div>${"x".repeat(2_000_000)}</div>`;
      vi.mocked(getCellContextData).mockReturnValue({
        cellOutput: {
          outputType: "text",
          processedContent: null,
          imageUrl: null,
          output: { mimetype: "text/html", data: largeHtml },
        },
        consoleOutputs: null,
        cellName: "cell1",
      } as never);

      const result = await tool.handler({}, toolContext as never);

      expect(result.status).toBe("success");
      const output = result.cellsToOutput?.[cellId1]?.cellOutput ?? "";
      expect(output).toContain("HTML Output:");
      expect(output).toContain("text/html");
      expect(output.length).toBeLessThan(200);
      expect(output).not.toContain(largeHtml);
    });

    it("should truncate large text output to MAX_TEXT_OUTPUT_CHARS", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: "print(big_string)", edited: true },
        },
      });
      store.set(notebookAtom, notebook);

      vi.mocked(runCells).mockImplementation(async () => {
        const updatedNotebook = store.get(notebookAtom);
        updatedNotebook.cellRuntime[cellId1] = {
          ...updatedNotebook.cellRuntime[cellId1],
          status: "idle",
        };
        store.set(notebookAtom, updatedNotebook);
      });

      const largeText = "a".repeat(10_000);
      vi.mocked(getCellContextData).mockReturnValue({
        cellOutput: {
          outputType: "text",
          processedContent: largeText,
          imageUrl: null,
          output: { mimetype: "text/plain", data: largeText },
        },
        consoleOutputs: null,
        cellName: "cell1",
      } as never);

      const result = await tool.handler({}, toolContext as never);

      const output = result.cellsToOutput?.[cellId1]?.cellOutput ?? "";
      expect(output).toContain("[TRUNCATED:");
      expect(output).toContain("Full output visible in the notebook UI.");
      // Output should be capped (2000 chars content + "Output:\n" prefix + truncation message)
      expect(output.length).toBeLessThan(2200);
    });

    it("should omit output for cells that exceed total output budget", async () => {
      const cellIds = Array.from({ length: 25 }, (_, i) =>
        cellId(`budget-cell-${i}`),
      );
      const cellData: Record<string, { code: string; edited: boolean }> = {};
      for (const id of cellIds) {
        cellData[id] = { code: "x = 1", edited: true };
      }

      const notebook = MockNotebook.notebookState({ cellData });
      store.set(notebookAtom, notebook);

      vi.mocked(runCells).mockImplementation(async () => {
        const updatedNotebook = store.get(notebookAtom);
        for (const id of cellIds) {
          updatedNotebook.cellRuntime[id] = {
            ...updatedNotebook.cellRuntime[id],
            status: "idle",
          };
        }
        store.set(notebookAtom, updatedNotebook);
      });

      // Each cell produces ~2008 chars of formatted output ("Output:\n" + 2000 chars).
      // After 20 cells the running total exceeds MAX_TOOL_OUTPUT_CHARS (40,000).
      const content = "a".repeat(2000);
      vi.mocked(getCellContextData).mockReturnValue({
        cellOutput: {
          outputType: "text",
          processedContent: content,
          imageUrl: null,
          output: { mimetype: "text/plain", data: content },
        },
        consoleOutputs: null,
        cellName: "cell",
      } as never);

      const result = await tool.handler({}, toolContext as never);

      expect(result.cellsToOutput?.[cellIds[0]]?.cellOutput).toContain(
        "Output:",
      );
      expect(result.cellsToOutput?.[cellIds[24]]?.cellOutput).toBe(
        "Cell executed (output omitted due to context limits).",
      );
    });

    it("should use higher truncation limit for error outputs", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: "raise Exception()", edited: true },
        },
      });
      store.set(notebookAtom, notebook);

      vi.mocked(runCells).mockImplementation(async () => {
        const updatedNotebook = store.get(notebookAtom);
        updatedNotebook.cellRuntime[cellId1] = {
          ...updatedNotebook.cellRuntime[cellId1],
          status: "idle",
        };
        store.set(notebookAtom, updatedNotebook);
      });

      // 2500 chars sits between MAX_TEXT_OUTPUT_CHARS (2000) and MAX_ERROR_OUTPUT_CHARS (3000)
      const errorContent = "E".repeat(2500);
      vi.mocked(getCellContextData).mockReturnValue({
        cellOutput: {
          outputType: "text",
          processedContent: errorContent,
          imageUrl: null,
          output: {
            mimetype: "application/vnd.marimo+error",
            data: errorContent,
          },
        },
        consoleOutputs: null,
        cellName: "cell1",
      } as never);

      const result = await tool.handler({}, toolContext as never);

      const output = result.cellsToOutput?.[cellId1]?.cellOutput ?? "";
      expect(output).not.toContain("[TRUNCATED:");
      expect(output).toContain(errorContent);
    });

    it("should truncate large console output", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: 'print("x" * 10000)', edited: true },
        },
      });
      store.set(notebookAtom, notebook);

      vi.mocked(runCells).mockImplementation(async () => {
        const updatedNotebook = store.get(notebookAtom);
        updatedNotebook.cellRuntime[cellId1] = {
          ...updatedNotebook.cellRuntime[cellId1],
          status: "idle",
        };
        store.set(notebookAtom, updatedNotebook);
      });

      const largeConsoleText = "x".repeat(10_000);
      vi.mocked(getCellContextData).mockReturnValue({
        cellOutput: null,
        consoleOutputs: [
          {
            outputType: "text",
            processedContent: largeConsoleText,
            imageUrl: null,
            output: { mimetype: "text/plain", data: largeConsoleText },
          },
        ],
        cellName: "cell1",
      } as never);

      const result = await tool.handler({}, toolContext as never);

      const consoleOutput =
        result.cellsToOutput?.[cellId1]?.consoleOutput ?? "";
      expect(consoleOutput).toContain("[TRUNCATED:");
      expect(consoleOutput.length).toBeLessThan(2200);
    });
  });

  describe("cell execution completion", () => {
    it("should complete immediately if cells are already idle", async () => {
      const notebook = MockNotebook.notebookState({
        cellData: {
          [cellId1]: { code: "x = 1", edited: true },
        },
      });

      // Set cell runtime to already be idle
      notebook.cellRuntime[cellId1] = {
        ...notebook.cellRuntime[cellId1],
        status: "idle",
      };
      store.set(notebookAtom, notebook);

      // Mock runCells to do nothing (cells already idle)
      vi.mocked(runCells).mockResolvedValue();

      // Mock getCellContextData
      vi.mocked(getCellContextData).mockReturnValue({
        cellOutput: {
          outputType: "text",
          processedContent: "1",
          imageUrl: null,
          output: {},
        },
        consoleOutputs: null,
        cellName: "cell1",
      } as never);

      const result = await tool.handler({}, toolContext as never);

      expect(result.status).toBe("success");
      expect(result.cellsToOutput).toBeDefined();
    });
  });
});
