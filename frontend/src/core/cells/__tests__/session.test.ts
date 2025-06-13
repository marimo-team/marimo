/* Copyright 2024 Marimo. All rights reserved. */

import type * as api from "@marimo-team/marimo-api";
/* eslint-disable @typescript-eslint/no-explicit-any */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { parseOutline } from "@/core/dom/outline";
import { MultiColumn, visibleForTesting } from "@/utils/id-tree";
import { invariant } from "@/utils/invariant";
import { Logger } from "@/utils/Logger";
import type { CellId } from "../ids";
import { notebookStateFromSession } from "../session";

// Mock dependencies
vi.mock("@/utils/Logger", () => ({
  Logger: {
    error: vi.fn(),
    warn: vi.fn(),
    debug: vi.fn(),
  },
}));

vi.mock("@/core/dom/outline", () => ({
  parseOutline: vi.fn(),
}));

type SessionCell = api.Session["NotebookSessionV1"]["cells"][0];
type NotebookCell = api.Notebook["NotebookV1"]["cells"][0];

// Test constants
const CELL_1 = "cell-1" as CellId;

describe("notebookStateFromSession", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    visibleForTesting.reset();
  });

  // Test data factories
  const createSessionCell = (
    id: string,
    outputs: SessionCell["outputs"] = [],
    console: SessionCell["console"] = [],
  ): SessionCell => ({
    id,
    code_hash: null,
    outputs,
    console,
  });

  const createNotebookCell = (
    id: string,
    code: string | null = null,
    name: string | null = null,
    config: NotebookCell["config"] | null = null,
  ): NotebookCell => ({
    id,
    code,
    name,
    config: {
      column: config?.column ?? null,
      disabled: config?.disabled ?? null,
      hide_code: config?.hide_code ?? null,
    },
  });

  const createSession = (
    cells: SessionCell[],
  ): api.Session["NotebookSessionV1"] => ({
    version: "1",
    metadata: { marimo_version: "1" },
    cells,
  });

  const createNotebook = (
    cells: NotebookCell[],
  ): api.Notebook["NotebookV1"] => ({
    version: "1",
    metadata: { marimo_version: "1" },
    cells,
  });

  describe("validation", () => {
    it("logs error for both session and notebook null/undefined", () => {
      const result = notebookStateFromSession(null, null);
      expect(result).toBeNull();
    });

    it("logs error when session and notebook have different cells", () => {
      const session = createSession([createSessionCell("cell-1")]);
      const notebook = createNotebook([createNotebookCell("cell-2")]);

      const result = notebookStateFromSession(session, notebook);

      expect(Logger.error).toHaveBeenCalledWith(
        "Session and notebook must have the same cells if both are provided",
      );
      expect(result).toBeNull();
    });
  });

  describe("null/undefined inputs", () => {
    it("returns null when both session and notebook are null", () => {
      const result = notebookStateFromSession(null, null);
      expect(result).toBeNull();
    });

    it("returns null when both session and notebook are undefined", () => {
      const result = notebookStateFromSession(undefined, undefined);
      expect(result).toBeNull();
    });

    it("returns null when session is null and notebook is undefined", () => {
      const result = notebookStateFromSession(null, undefined);
      expect(result).toBeNull();
    });
  });

  describe("session only scenarios", () => {
    it("creates state from session with single cell", () => {
      const session = createSession([createSessionCell("cell-1")]);
      const result = notebookStateFromSession(session, null);

      expect(result).not.toBeNull();
      invariant(result, "result is null");
      expect(result.cellIds.inOrderIds).toEqual(
        MultiColumn.from([[CELL_1]]).inOrderIds,
      );
      expect(result.cellData[CELL_1]).toBeUndefined();
      expect(result.cellRuntime[CELL_1]).toBeDefined();
    });

    it("creates state from session with multiple cells", () => {
      const session = createSession([
        createSessionCell("cell-1"),
        createSessionCell("cell-2"),
      ]);
      const result = notebookStateFromSession(session, null);

      expect(result).not.toBeNull();
      invariant(result, "result is null");
      expect(result.cellIds.inOrderIds).toEqual(
        MultiColumn.from([["cell-1", "cell-2"]]).inOrderIds,
      );
      expect(Object.keys((result as any).cellData)).toEqual([]);
      expect(Object.keys((result as any).cellRuntime)).toEqual([
        "cell-1",
        "cell-2",
      ]);
    });

    it("handles error output in session cell", () => {
      const errorOutput = {
        type: "error" as const,
        ename: "ValueError",
        evalue: "Something went wrong",
        traceback: ["Traceback line 1"],
      };
      const session = createSession([
        createSessionCell("cell-1", [errorOutput]),
      ]);
      const result = notebookStateFromSession(session, null);

      expect(result).not.toBeNull();
      invariant(result, "result is null");
      expect(result.cellRuntime[CELL_1].output).toEqual({
        channel: "marimo-error",
        data: [
          {
            type: "unknown",
            msg: "Something went wrong",
          },
        ],
        mimetype: "application/vnd.marimo+error",
        timestamp: 0,
      });
    });

    it("handles data output in session cell", () => {
      const dataOutput = {
        type: "data" as const,
        data: {
          "text/plain": "Hello World",
        },
      };
      const session = createSession([
        createSessionCell("cell-1", [dataOutput]),
      ]);
      const result = notebookStateFromSession(session, null);

      expect(result).not.toBeNull();
      invariant(result, "result is null");
      expect(result.cellRuntime[CELL_1].output).toEqual({
        channel: "output",
        data: "Hello World",
        mimetype: "text/plain",
        timestamp: 0,
      });
    });

    it("handles console outputs in session cell", () => {
      const consoleOutputs = [
        { type: "stream", name: "stdout", text: "Hello stdout" } as const,
        { type: "stream", name: "stderr", text: "Hello stderr" } as const,
      ];
      const session = createSession([
        createSessionCell("cell-1", [], consoleOutputs),
      ]);
      const result = notebookStateFromSession(session, null);

      expect(result).not.toBeNull();
      invariant(result, "result is null");
      expect(result.cellRuntime[CELL_1].consoleOutputs).toEqual([
        {
          channel: "stdout",
          data: "Hello stdout",
          mimetype: "text/plain",
          timestamp: 0,
        },
        {
          channel: "stderr",
          data: "Hello stderr",
          mimetype: "text/plain",
          timestamp: 0,
        },
      ]);
    });

    it("calls parseOutline when output exists", () => {
      const mockOutline = { items: [] };
      vi.mocked(parseOutline).mockReturnValue(mockOutline);

      const dataOutput = {
        type: "data" as const,
        data: { "text/html": "<h1>Title</h1>" },
      };
      const session = createSession([
        createSessionCell("cell-1", [dataOutput]),
      ]);
      const result = notebookStateFromSession(session, null);

      expect(parseOutline).toHaveBeenCalledWith({
        channel: "output",
        data: "<h1>Title</h1>",
        mimetype: "text/html",
        timestamp: 0,
      });
      invariant(result, "result is null");
      expect(result.cellRuntime[CELL_1].outline).toBe(mockOutline);
    });

    it("sets outline to null when no output exists", () => {
      const session = createSession([createSessionCell("cell-1")]);
      const result = notebookStateFromSession(session, null);

      expect(parseOutline).not.toHaveBeenCalled();
      invariant(result, "result is null");
      expect(result.cellRuntime[CELL_1].outline).toBeNull();
    });
  });

  describe("notebook only scenarios", () => {
    it("creates state from notebook with single cell", () => {
      const notebook = createNotebook([
        createNotebookCell("cell-1", "print('hello')", "my_cell"),
      ]);
      const result = notebookStateFromSession(null, notebook);

      expect(result).not.toBeNull();
      invariant(result, "result is null");
      expect(result.cellIds.inOrderIds).toEqual(
        MultiColumn.from([[CELL_1]]).inOrderIds,
      );
      expect(result.cellData[CELL_1]).toEqual({
        id: "cell-1",
        name: "my_cell",
        code: "print('hello')",
        edited: false,
        lastCodeRun: null,
        lastExecutionTime: null,
        config: {
          hide_code: false,
          disabled: false,
          column: null,
        },
        serializedEditorState: null,
      });
    });

    it("creates state from notebook with custom config", () => {
      const notebook = createNotebook([
        createNotebookCell("cell-1", "code", "name", {
          hide_code: true,
          disabled: true,
          column: 1,
        }),
      ]);
      const result = notebookStateFromSession(null, notebook);

      expect(result).not.toBeNull();
      invariant(result, "result is null");
      expect(result.cellData[CELL_1].config).toEqual({
        hide_code: true,
        disabled: true,
        column: 1,
      });
    });

    it("handles null/undefined fields in notebook cell", () => {
      const notebookCell = {
        id: "cell-1",
        code: null,
        name: null,
        config: {
          hide_code: null,
          disabled: null,
          column: null,
        },
      };
      const notebook = createNotebook([notebookCell]);
      const result = notebookStateFromSession(null, notebook);

      expect(result).not.toBeNull();
      invariant(result, "result is null");
      expect(result.cellData[CELL_1]).toEqual({
        id: "cell-1",
        name: "",
        code: "",
        edited: false,
        lastCodeRun: null,
        lastExecutionTime: null,
        config: {
          hide_code: false,
          disabled: false,
          column: null,
        },
        serializedEditorState: null,
      });
    });
  });

  describe("both session and notebook scenarios", () => {
    it("creates state when session and notebook have matching cells", () => {
      const session = createSession([
        createSessionCell(
          "cell-1",
          [],
          [{ type: "stream", name: "stdout", text: "output" }],
        ),
      ]);
      const notebook = createNotebook([
        createNotebookCell("cell-1", "print('hello')", "my_cell"),
      ]);
      const result = notebookStateFromSession(session, notebook);

      expect(result).not.toBeNull();
      invariant(result, "result is null");
      expect(result.cellData[CELL_1]).toEqual({
        id: "cell-1",
        name: "my_cell",
        code: "print('hello')",
        edited: false,
        lastCodeRun: null,
        lastExecutionTime: null,
        config: {
          hide_code: false,
          disabled: false,
          column: null,
        },
        serializedEditorState: null,
      });
      expect(result.cellRuntime[CELL_1].consoleOutputs).toEqual([
        {
          channel: "stdout",
          data: "output",
          mimetype: "text/plain",
          timestamp: 0,
        },
      ]);
    });

    it("creates state when cell order differs but same cells", () => {
      const session = createSession([
        createSessionCell("cell-1"),
        createSessionCell("cell-2"),
      ]);
      const notebook = createNotebook([
        createNotebookCell("cell-2"),
        createNotebookCell("cell-1"),
      ]);

      const result = notebookStateFromSession(session, notebook);

      expect(result).not.toBeNull();
      invariant(result, "result is null");
      expect(result.cellIds.inOrderIds).toEqual(
        MultiColumn.from([["cell-2", "cell-1"]]).inOrderIds,
      );
    });

    it("creates state when session and notebook have identical cell arrays", () => {
      const session = createSession([
        createSessionCell("cell-1"),
        createSessionCell("cell-2"),
      ]);
      const notebook = createNotebook([
        createNotebookCell("cell-1"),
        createNotebookCell("cell-2"),
      ]);

      const result = notebookStateFromSession(session, notebook);

      expect(Logger.error).not.toHaveBeenCalled();
      expect(result).not.toBeNull();
      invariant(result, "result is null");
      expect(result.cellIds.inOrderIds).toEqual(
        MultiColumn.from([["cell-1", "cell-2"]]).inOrderIds,
      );
    });
  });

  describe("empty cells scenarios", () => {
    it("warns and returns null when session has empty cells array", () => {
      const session = createSession([]);
      const result = notebookStateFromSession(session, null);

      expect(Logger.warn).toHaveBeenCalledWith(
        "Session and notebook must have at least one cell",
      );
      expect(result).toBeNull();
    });

    it("warns and returns null when notebook has empty cells array", () => {
      const notebook = createNotebook([]);
      const result = notebookStateFromSession(null, notebook);

      expect(Logger.warn).toHaveBeenCalledWith(
        "Session and notebook must have at least one cell",
      );
      expect(result).toBeNull();
    });

    it("warns and returns null when both have empty cells arrays", () => {
      const session = createSession([]);
      const notebook = createNotebook([]);
      const result = notebookStateFromSession(session, notebook);

      expect(Logger.warn).toHaveBeenCalledWith(
        "Session and notebook must have at least one cell",
      );
      expect(result).toBeNull();
    });
  });

  describe("edge cases", () => {
    it("handles session cell with no outputs", () => {
      const session = createSession([createSessionCell("cell-1", [])]);
      const result = notebookStateFromSession(session, null);

      expect(result).not.toBeNull();
      invariant(result, "result is null");
      expect(result.cellRuntime[CELL_1].output).toBeNull();
      expect(result.cellRuntime[CELL_1].consoleOutputs).toEqual([]);
      expect(result.cellRuntime[CELL_1].outline).toBeNull();
    });

    it("handles session cell with empty console array", () => {
      const session = createSession([createSessionCell("cell-1", [], [])]);
      const result = notebookStateFromSession(session, null);

      expect(result).not.toBeNull();
      invariant(result, "result is null");
      expect(result.cellRuntime[CELL_1].consoleOutputs).toEqual([]);
    });

    it("handles session cell with multiple outputs (uses first one)", () => {
      const outputs = [
        { type: "data" as const, data: { "text/plain": "First" } },
        { type: "data" as const, data: { "text/plain": "Second" } },
      ];
      const session = createSession([createSessionCell("cell-1", outputs)]);
      const result = notebookStateFromSession(session, null);

      expect(result).not.toBeNull();
      invariant(result, "result is null");
      expect(result.cellRuntime[CELL_1].output).toEqual({
        channel: "output",
        data: "First",
        mimetype: "text/plain",
        timestamp: 0,
      });
    });

    it("handles data output with multiple mimetypes (uses first one)", () => {
      const dataOutput = {
        type: "data" as const,
        data: {
          "text/plain": "Plain text",
          "text/html": "<p>HTML</p>",
        },
      };
      const session = createSession([
        createSessionCell("cell-1", [dataOutput]),
      ]);
      const result = notebookStateFromSession(session, null);

      expect(result).not.toBeNull();
      invariant(result, "result is null");
      expect(result.cellRuntime[CELL_1].output).toEqual({
        channel: "output",
        data: "Plain text",
        mimetype: "text/plain",
        timestamp: 0,
      });
    });

    it("handles data output with empty data object", () => {
      const dataOutput = {
        type: "data" as const,
        data: {},
      };
      const session = createSession([
        createSessionCell("cell-1", [dataOutput]),
      ]);
      const result = notebookStateFromSession(session, null);

      expect(result).not.toBeNull();
      invariant(result, "result is null");
      expect(result.cellRuntime[CELL_1].output).toEqual({
        channel: "output",
        data: undefined,
        mimetype: undefined,
        timestamp: 0,
      });
    });

    it("returns correct structure with all expected properties", () => {
      const session = createSession([createSessionCell("cell-1")]);
      const result = notebookStateFromSession(session, null);

      expect(result).not.toBeNull();
      invariant(result, "result is null");
      expect(result).toHaveProperty("cellIds");
      expect(result).toHaveProperty("cellData");
      expect(result).toHaveProperty("cellRuntime");
      expect(result).toHaveProperty("cellHandles");
      expect(result).toHaveProperty("history");
      expect(result).toHaveProperty("scrollKey");
      expect(result).toHaveProperty("cellLogs");

      expect(result.cellHandles).toEqual({});
      expect(result.history).toEqual([]);
      expect(result.scrollKey).toBeNull();
      expect(result.cellLogs).toEqual([]);
    });
  });
});
