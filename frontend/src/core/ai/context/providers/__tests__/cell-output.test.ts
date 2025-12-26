/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Mocks } from "@/__mocks__/common";

// Mock the external dependencies
vi.mock("html-to-image", () => ({
  toPng: vi.fn().mockResolvedValue("data:image/png;base64,mockbase64data"),
}));

vi.mock("@/utils/Logger", () => ({
  Logger: Mocks.quietLogger(),
}));

import type { NotebookState } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import type { OutputMessage } from "@/core/kernel/messages";
import type { JotaiStore } from "@/core/state/jotai";
import { CellOutputContextProvider, getCellContextData } from "../cell-output";

// Test helper to create mock store
function createMockStore(notebook: NotebookState): JotaiStore {
  const store = {
    get: vi.fn().mockReturnValue(notebook),
  } as unknown as JotaiStore;
  return store;
}

describe("CellOutputContextProvider", () => {
  let provider: CellOutputContextProvider;
  let mockStore: JotaiStore;
  let mockNotebook: NotebookState;

  beforeEach(() => {
    // Create a basic mock notebook state
    mockNotebook = {
      cellIds: {
        inOrderIds: ["cell1" as CellId, "cell2" as CellId, "cell3" as CellId],
      },
      cellData: {
        cell1: {
          id: "cell1" as CellId,
          name: "My Cell",
          code: "print('hello world')",
        },
        cell2: {
          id: "cell2" as CellId,
          name: "",
          code: "import matplotlib.pyplot as plt\nplt.plot([1,2,3])",
        },
        cell3: {
          id: "cell3" as CellId,
          name: "Empty Cell",
          code: "# no output",
        },
      },
      cellRuntime: {
        cell1: {
          output: {
            mimetype: "text/plain",
            data: "hello world",
          } as OutputMessage,
        },
        cell2: {
          output: {
            mimetype: "image/png",
            data: "base64imagedata",
          } as OutputMessage,
        },
        cell3: {
          output: null,
        },
      },
    } as unknown as NotebookState;

    mockStore = createMockStore(mockNotebook);
    provider = new CellOutputContextProvider(mockStore);
  });

  describe("basic properties", () => {
    it("should have correct title and context type", () => {
      expect(provider.title).toBe("Cell Outputs");
      expect(provider.contextType).toBe("cell-output");
      expect(provider.mentionPrefix).toBe("@");
    });
  });

  describe("getItems", () => {
    it("should return only cells with outputs", () => {
      const items = provider.getItems();

      // Should have 2 items (cell1 and cell2, but not cell3 which has no output)
      expect(items).toHaveLength(2);

      const cellIds = items.map((item) => item.data.cellId);
      expect(cellIds).toContain("cell1");
      expect(cellIds).toContain("cell2");
      expect(cellIds).not.toContain("cell3");
    });

    it("should correctly identify text vs media outputs", () => {
      const items = provider.getItems();

      const textItem = items.find((item) => item.data.cellId === "cell1");
      const mediaItem = items.find((item) => item.data.cellId === "cell2");

      expect(textItem?.data.cellOutput.outputType).toBe("text");
      expect(mediaItem?.data.cellOutput.outputType).toBe("media");
    });

    it("should process text content correctly", () => {
      const items = provider.getItems();
      const textItem = items.find((item) => item.data.cellId === "cell1");

      expect(textItem?.data.cellOutput.processedContent).toBe("hello world");
    });

    it("should mark media items for download when no direct URL available", () => {
      const items = provider.getItems();
      const mediaItem = items.find((item) => item.data.cellId === "cell2");

      expect(mediaItem?.data.cellOutput.shouldDownloadImage).toBe(true);
      expect(mediaItem?.data.cellOutput.imageUrl).toBeUndefined();
    });

    it("should include cell code and names", () => {
      const items = provider.getItems();

      const item1 = items.find((item) => item.data.cellId === "cell1");
      const item2 = items.find((item) => item.data.cellId === "cell2");

      expect(item1?.data.cellName).toBe("My Cell");
      expect(item1?.data.cellCode).toBe("print('hello world')");

      expect(item2?.data.cellName).toBe("cell-1");
      expect(item2?.data.cellCode).toBe(
        "import matplotlib.pyplot as plt\nplt.plot([1,2,3])",
      );
    });
  });

  describe("formatContext", () => {
    it("should format text output context correctly", () => {
      const items = provider.getItems();
      const textItem = items.find((item) => item.data.cellId === "cell1");

      if (!textItem) {
        throw new Error("Text item not found");
      }

      const context = provider.formatContext(textItem);

      expect(context).toContain("cell-output");
      expect(context).toContain("My Cell");
      expect(context).toContain("Cell Code:");
      expect(context).toContain("print('hello world')");
      expect(context).toContain("Output:");
      expect(context).toContain("hello world");

      expect(context).toMatchSnapshot("text-output-context");
    });

    it("should format media output context correctly", () => {
      const items = provider.getItems();
      const mediaItem = items.find((item) => item.data.cellId === "cell2");

      if (!mediaItem) {
        throw new Error("Media item not found");
      }

      const context = provider.formatContext(mediaItem);

      expect(context).toContain("cell-output");
      expect(context).toContain("cell-1");
      expect(context).toContain("Cell Code:");
      expect(context).toContain("import matplotlib.pyplot as plt");
      expect(context).toContain("Media Output: Contains image/png content");

      expect(context).toMatchSnapshot("media-output-context");
    });
  });

  describe("formatCompletion", () => {
    it("should create proper completion object", () => {
      const items = provider.getItems();
      const item = items[0];

      const completion = provider.formatCompletion(item);

      expect(completion.label).toMatch(/@.+/);
      expect(completion.displayLabel).toBe(item.data.cellName);
      expect(completion.detail).toContain("output");
      expect(completion.type).toBe("cell-output");
      expect(typeof completion.info).toBe("function");
    });
  });
});

// Test utility functions separately
describe("Cell output utility functions", () => {
  // We need to extract these functions to test them, or make them exported
  // For now, let's test through the public interface

  describe("media type detection", () => {
    let provider: CellOutputContextProvider;
    let mockStore: JotaiStore;

    beforeEach(() => {
      const mockNotebook = {
        cellIds: { inOrderIds: [] },
        cellData: {},
        cellRuntime: {},
      } as unknown as NotebookState;

      mockStore = createMockStore(mockNotebook);
      provider = new CellOutputContextProvider(mockStore);
    });

    it("should detect image mimetypes as media", () => {
      const testCases = [
        { mimetype: "image/png", data: "test", expected: "media" },
        { mimetype: "image/jpeg", data: "test", expected: "media" },
        { mimetype: "image/gif", data: "test", expected: "media" },
        { mimetype: "image/svg+xml", data: "test", expected: "media" },
      ];

      for (const testCase of testCases) {
        mockStore = createMockStore({
          cellIds: { inOrderIds: ["test" as CellId] },
          cellData: {
            test: { id: "test" as CellId, name: "", code: "" },
          },
          cellRuntime: {
            test: {
              output: {
                mimetype: testCase.mimetype,
                data: testCase.data,
              } as OutputMessage,
            },
          },
        } as unknown as NotebookState);

        provider = new CellOutputContextProvider(mockStore);
        const items = provider.getItems();

        expect(items[0]?.data.cellOutput.outputType).toBe(testCase.expected);
      }
    });

    it("should detect HTML with media tags as media", () => {
      const htmlWithImage = '<div><img src="test.png" /></div>';
      const htmlWithCanvas = '<canvas width="100" height="100"></canvas>';
      const htmlWithSvg = '<svg><circle r="50" /></svg>';

      const testCases = [
        { data: htmlWithImage, expected: "media" },
        { data: htmlWithCanvas, expected: "media" },
        { data: htmlWithSvg, expected: "media" },
        { data: "<p>Just text</p>", expected: "text" },
      ];

      for (const testCase of testCases) {
        mockStore = createMockStore({
          cellIds: { inOrderIds: ["test" as CellId] },
          cellData: {
            test: { id: "test" as CellId, name: "", code: "" },
          },
          cellRuntime: {
            test: {
              output: {
                mimetype: "text/html",
                data: testCase.data,
              } as OutputMessage,
            },
          },
        } as unknown as NotebookState);

        provider = new CellOutputContextProvider(mockStore);
        const items = provider.getItems();

        expect(items[0]?.data.cellOutput.outputType).toBe(testCase.expected);
      }
    });

    it("should detect text mimetypes correctly", () => {
      const testCases = [
        { mimetype: "text/plain", expected: "text" },
        {
          mimetype: "text/html",
          data: "<p>No media tags</p>",
          expected: "text",
        },
        { mimetype: "application/json", expected: "text" },
      ];

      for (const testCase of testCases) {
        mockStore = createMockStore({
          cellIds: { inOrderIds: ["test" as CellId] },
          cellData: {
            test: { id: "test" as CellId, name: "", code: "" },
          },
          cellRuntime: {
            test: {
              output: {
                mimetype: testCase.mimetype,
                data: testCase.data || "test data",
              } as OutputMessage,
            },
          },
        } as unknown as NotebookState);

        provider = new CellOutputContextProvider(mockStore);
        const items = provider.getItems();

        expect(items[0]?.data.cellOutput.outputType).toBe(testCase.expected);
      }
    });
  });

  describe("HTML content parsing", () => {
    let provider: CellOutputContextProvider;
    let mockStore: JotaiStore;
    let originalCreateElement: typeof document.createElement;

    beforeEach(() => {
      // Save original createElement
      originalCreateElement = document.createElement;

      // Mock DOM methods for HTML parsing
      const mockDiv = {
        innerHTML: "",
        textContent: "",
        innerText: "",
      };

      global.document = {
        createElement: vi.fn().mockReturnValue(mockDiv),
      } as unknown as Document;

      const mockNotebook = {
        cellIds: { inOrderIds: [] },
        cellData: {},
        cellRuntime: {},
      } as unknown as NotebookState;

      mockStore = createMockStore(mockNotebook);
      provider = new CellOutputContextProvider(mockStore);
    });

    afterEach(() => {
      // Restore original createElement to prevent mock pollution
      if (originalCreateElement) {
        document.createElement = originalCreateElement;
      }
    });

    it("should extract text content from HTML", () => {
      const htmlContent = "<p>Hello <strong>world</strong>!</p>";

      // Mock the DOM parsing result
      const mockDiv = {
        innerHTML: "",
        textContent: "Hello world!",
        innerText: "Hello world!",
      };

      (
        global.document.createElement as ReturnType<typeof vi.fn>
      ).mockReturnValue(mockDiv);

      mockStore = createMockStore({
        cellIds: { inOrderIds: ["test" as CellId] },
        cellData: {
          test: { id: "test" as CellId, name: "", code: "" },
        },
        cellRuntime: {
          test: {
            output: {
              mimetype: "text/html",
              data: htmlContent,
            } as OutputMessage,
          },
        },
      } as unknown as NotebookState);

      provider = new CellOutputContextProvider(mockStore);
      const items = provider.getItems();

      expect(items[0]?.data.cellOutput.processedContent).toBe("Hello world!");
    });
  });

  describe("getCellContextData", () => {
    let mockNotebook: NotebookState;

    beforeEach(() => {
      mockNotebook = {
        cellIds: {
          inOrderIds: ["cell1" as CellId, "cell2" as CellId],
        },
        cellData: {
          cell1: {
            id: "cell1" as CellId,
            name: "My Named Cell",
            code: "x = 42",
          },
          cell2: {
            id: "cell2" as CellId,
            name: "",
            code: "y = x * 2",
          },
        },
        cellRuntime: {
          cell1: {
            output: {
              mimetype: "text/plain",
              data: "42",
            } as OutputMessage,
            consoleOutputs: [],
          },
          cell2: {
            output: null,
            consoleOutputs: [
              {
                mimetype: "text/plain",
                data: "console log message",
              } as OutputMessage,
            ],
          },
        },
      } as unknown as NotebookState;
    });

    it("should extract basic cell data", () => {
      const result = getCellContextData("cell1" as CellId, mockNotebook);

      expect(result.cellId).toBe("cell1");
      expect(result.cellName).toBe("My Named Cell");
      expect(result.cellCode).toBe("x = 42");
    });

    it("should generate cell name for unnamed cells", () => {
      const result = getCellContextData("cell2" as CellId, mockNotebook);

      expect(result.cellName).toBe("cell-1"); // 0-indexed, so cell2 is at index 1
    });

    it("should include cell output when present", () => {
      const result = getCellContextData("cell1" as CellId, mockNotebook);

      expect(result.cellOutput).toBeDefined();
      expect(result.cellOutput?.outputType).toBe("text");
      expect(result.cellOutput?.processedContent).toBe("42");
    });

    it("should not include cell output when not present", () => {
      const result = getCellContextData("cell2" as CellId, mockNotebook);

      expect(result.cellOutput).toBeUndefined();
    });

    it("should not include console outputs by default", () => {
      const result = getCellContextData("cell2" as CellId, mockNotebook);

      expect(result.consoleOutputs).toBeUndefined();
    });

    it("should include console outputs when opted in", () => {
      const result = getCellContextData("cell2" as CellId, mockNotebook, {
        includeConsoleOutput: true,
      });

      expect(result.consoleOutputs).toBeDefined();
      expect(result.consoleOutputs).toHaveLength(1);
      expect(result.consoleOutputs?.[0]?.processedContent).toBe(
        "console log message",
      );
    });

    it("should filter out empty console outputs", () => {
      const cell2Runtime = mockNotebook.cellRuntime["cell2" as CellId];
      if (cell2Runtime) {
        (cell2Runtime as { consoleOutputs: OutputMessage[] }).consoleOutputs = [
          {
            mimetype: "text/plain",
            data: "valid output",
          } as OutputMessage,
          {
            mimetype: "text/plain",
            data: "",
          } as OutputMessage,
        ];
      }

      const result = getCellContextData("cell2" as CellId, mockNotebook, {
        includeConsoleOutput: true,
      });

      expect(result.consoleOutputs).toHaveLength(1);
      expect(result.consoleOutputs?.[0]?.processedContent).toBe("valid output");
    });

    it("should handle cells with both cell output and console outputs", () => {
      const cell1Runtime = mockNotebook.cellRuntime["cell1" as CellId];
      if (cell1Runtime) {
        (cell1Runtime as { consoleOutputs: OutputMessage[] }).consoleOutputs = [
          {
            mimetype: "text/plain",
            data: "debug message",
          } as OutputMessage,
        ];
      }

      const result = getCellContextData("cell1" as CellId, mockNotebook, {
        includeConsoleOutput: true,
      });

      expect(result.cellOutput).toBeDefined();
      expect(result.cellOutput?.processedContent).toBe("42");
      expect(result.consoleOutputs).toHaveLength(1);
      expect(result.consoleOutputs?.[0]?.processedContent).toBe(
        "debug message",
      );
    });

    it("should handle empty console outputs array", () => {
      const result = getCellContextData("cell1" as CellId, mockNotebook, {
        includeConsoleOutput: true,
      });

      expect(result.consoleOutputs).toEqual([]);
    });

    it("should handle media outputs in cell output", () => {
      const cell1Runtime = mockNotebook.cellRuntime["cell1" as CellId];
      if (cell1Runtime) {
        (cell1Runtime as { output: OutputMessage | null }).output = {
          mimetype: "image/png",
          data: "data:image/png;base64,test",
        } as OutputMessage;
      }

      const result = getCellContextData("cell1" as CellId, mockNotebook);

      expect(result.cellOutput).toBeDefined();
      expect(result.cellOutput?.outputType).toBe("media");
      expect(result.cellOutput?.imageUrl).toBe("data:image/png;base64,test");
    });

    it("should handle media outputs in console outputs", () => {
      const cell2Runtime = mockNotebook.cellRuntime["cell2" as CellId];
      if (cell2Runtime) {
        (cell2Runtime as { consoleOutputs: OutputMessage[] }).consoleOutputs = [
          {
            mimetype: "image/png",
            data: "https://example.com/image.png",
          } as OutputMessage,
        ];
      }

      const result = getCellContextData("cell2" as CellId, mockNotebook, {
        includeConsoleOutput: true,
      });

      expect(result.consoleOutputs).toHaveLength(1);
      expect(result.consoleOutputs?.[0]?.outputType).toBe("media");
      expect(result.consoleOutputs?.[0]?.imageUrl).toBe(
        "https://example.com/image.png",
      );
    });
  });
});
