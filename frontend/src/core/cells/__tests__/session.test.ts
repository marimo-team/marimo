/* Copyright 2026 Marimo. All rights reserved. */

import type * as api from "@marimo-team/marimo-api";
/* oxlint-disable typescript/no-explicit-any */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Mocks } from "@/__mocks__/common";
import { cellId } from "@/__tests__/branded";
import { parseOutline } from "@/core/dom/outline";
import { visibleForTesting } from "@/utils/id-tree";
import { invariant } from "@/utils/invariant";
import { Logger } from "@/utils/Logger";
import { SETUP_CELL_ID } from "../ids";
import { readExport } from "../session";

// Mock dependencies
vi.mock("@/utils/Logger", () => ({ Logger: Mocks.quietLogger() }));

vi.mock("@/core/dom/outline", () => ({
  parseOutline: vi.fn(),
}));

type SessionCell = api.Session["NotebookSessionV1"]["cells"][0];
type NotebookCell = api.Notebook["NotebookV1"]["cells"][0];

// Test constants
const CELL_1 = cellId("cell-1");

/** The snapshot's record of a cell. */
function cellIn(result: ReturnType<typeof readExport>, id: string) {
  const cell = result.snapshot?.cells.find((cell) => cell.id === id);
  invariant(cell, `no cell ${id}`);
  return cell;
}

describe("readExport", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    visibleForTesting.reset();
  });

  // Test data factories
  const createSessionCell = (
    id: string,
    outputs: SessionCell["outputs"] = [],
    console: SessionCell["console"] = [],
    code_hash: string | null = null,
  ): SessionCell => ({
    id,
    code_hash,
    outputs,
    console,
  });

  const createNotebookCell = (
    id: string,
    {
      code = null,
      name = null,
      config = null,
      code_hash = null,
    }: {
      code?: string | null;
      name?: string | null;
      config?: NotebookCell["config"] | null;
      code_hash?: string | null;
    } = {},
  ): NotebookCell => ({
    id,
    code,
    code_hash: code_hash,
    name,
    config: {
      column: config?.column ?? null,
      disabled: config?.disabled ?? null,
      hide_code: config?.hide_code ?? null,
      expand_output: config?.expand_output ?? null,
    },
  });

  const createSession = (
    cells: SessionCell[],
  ): api.Session["NotebookSessionV1"] => ({
    version: "1",
    metadata: { marimo_version: "1", script_metadata_hash: null },
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
      const result = readExport({
        session: null,
        notebook: null,
        filename: null,
        appConfig: {},
      });
      expect(result.snapshot).toBeNull();
    });

    it("logs error when session and notebook have different cells", () => {
      const session = createSession([createSessionCell("cell-1")]);
      const notebook = createNotebook([createNotebookCell("cell-2", {})]);

      const result = readExport({
        session: session,
        notebook: notebook,
        filename: null,
        appConfig: {},
      });

      expect(Logger.warn).toHaveBeenCalledWith(
        "Session and notebook have different cells, attempted merge.",
      );
      // Should have the same cell structure as notebook
      invariant(result.snapshot, "no snapshot");
      expect(result.snapshot.document.order).toEqual(["cell-2"]);
    });
  });

  describe("null/undefined inputs", () => {
    it("returns null when both session and notebook are null", () => {
      const result = readExport({
        session: null,
        notebook: null,
        filename: null,
        appConfig: {},
      });
      expect(result.snapshot).toBeNull();
    });

    it("returns null when both session and notebook are undefined", () => {
      const result = readExport({
        session: undefined,
        notebook: undefined,
        filename: null,
        appConfig: {},
      });
      expect(result.snapshot).toBeNull();
    });

    it("returns null when session is null and notebook is undefined", () => {
      const result = readExport({
        session: null,
        notebook: undefined,
        filename: null,
        appConfig: {},
      });
      expect(result.snapshot).toBeNull();
    });
  });

  describe("session only scenarios", () => {
    it("creates state from session with single cell", () => {
      const session = createSession([createSessionCell("cell-1")]);
      const result = readExport({
        session: session,
        notebook: null,
        filename: null,
        appConfig: {},
      });

      invariant(result.snapshot, "no snapshot");
      expect(result.snapshot.document.order).toEqual([CELL_1]);
      // The session knows outputs, not source; the host withholds it as null.
      expect(cellIn(result, CELL_1).code).toBeNull();
      expect(result.cellRuntime[CELL_1]).toBeDefined();
    });

    it("creates state from session with multiple cells", () => {
      const session = createSession([
        createSessionCell("cell-1"),
        createSessionCell("cell-2"),
      ]);
      const result = readExport({
        session: session,
        notebook: null,
        filename: null,
        appConfig: {},
      });

      invariant(result.snapshot, "no snapshot");
      expect(result.snapshot.document.order).toEqual(["cell-1", "cell-2"]);
      expect(result.snapshot.cells.map((cell) => cell.id)).toEqual([
        "cell-1",
        "cell-2",
      ]);
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
      const result = readExport({
        session: session,
        notebook: null,
        filename: null,
        appConfig: {},
      });

      invariant(result.snapshot, "no snapshot");
      expect(result.cellRuntime[CELL_1].output).toEqual({
        channel: "marimo-error",
        data: [
          {
            type: "exception",
            exception_type: "ValueError",
            msg: "Something went wrong",
            raising_cell: null,
            traceback: "Traceback line 1",
          },
        ],
        mimetype: "application/vnd.marimo+error",
        timestamp: 0,
      });
    });

    it("restores matching code from the session", () => {
      const code = "raise ValueError('cached failure')";
      const session = createSession([
        createSessionCell(
          "cell-1",
          [
            {
              type: "error",
              ename: "ValueError",
              evalue: "cached failure",
              traceback: ["Traceback\n", "ValueError: cached failure"],
              code,
            },
          ],
          [
            {
              type: "stream",
              name: "stderr",
              text: "ValueError: cached <failure>",
              mimetype: "application/vnd.marimo+traceback",
              traceback_format: "text",
              code,
            },
          ],
        ),
      ]);
      const state = readExport({
        session: session,
        notebook: null,
        filename: null,
        appConfig: {},
      });
      invariant(state.snapshot, "no snapshot");
      expect(state.cellRuntime[CELL_1].output).toMatchObject({
        code,
        data: [
          {
            type: "exception",
            exception_type: "ValueError",
            msg: "cached failure",
            traceback: "Traceback\nValueError: cached failure",
          },
        ],
      });
      expect(state.cellRuntime[CELL_1].consoleOutputs[0].code).toBe(code);
      expect(state.cellRuntime[CELL_1].consoleOutputs[0]).toMatchObject({
        traceback_format: "text",
        data: "ValueError: cached <failure>",
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
      const result = readExport({
        session: session,
        notebook: null,
        filename: null,
        appConfig: {},
      });

      invariant(result.snapshot, "no snapshot");
      expect(result.cellRuntime[CELL_1].output).toEqual({
        channel: "output",
        data: "Hello World",
        mimetype: "text/plain",
        timestamp: 0,
      });
    });

    it("handles console outputs in session cell", () => {
      const consoleOutputs = [
        {
          type: "stream",
          name: "stdout",
          text: "Hello stdout",
          mimetype: "text/plain",
        } as const,
        {
          type: "stream",
          name: "stderr",
          text: "Hello stderr",
          mimetype: "text/plain",
        } as const,
      ];
      const session = createSession([
        createSessionCell("cell-1", [], consoleOutputs),
      ]);
      const result = readExport({
        session: session,
        notebook: null,
        filename: null,
        appConfig: {},
      });

      invariant(result.snapshot, "no snapshot");
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
      const result = readExport({
        session: session,
        notebook: null,
        filename: null,
        appConfig: {},
      });

      expect(parseOutline).toHaveBeenCalledWith({
        channel: "output",
        data: "<h1>Title</h1>",
        mimetype: "text/html",
        timestamp: 0,
      });
      invariant(result.snapshot, "no snapshot");
      expect(result.cellRuntime[CELL_1].outline).toBe(mockOutline);
    });

    it("sets outline to null when no output exists", () => {
      const session = createSession([createSessionCell("cell-1")]);
      const result = readExport({
        session: session,
        notebook: null,
        filename: null,
        appConfig: {},
      });

      expect(parseOutline).not.toHaveBeenCalled();
      invariant(result.snapshot, "no snapshot");
      expect(result.cellRuntime[CELL_1].outline).toBeNull();
    });
  });

  describe("notebook only scenarios", () => {
    it("creates state from notebook with single cell", () => {
      const notebook = createNotebook([
        createNotebookCell("cell-1", {
          code: "print('hello')",
          name: "my_cell",
        }),
      ]);
      const result = readExport({
        session: null,
        notebook: notebook,
        filename: null,
        appConfig: {},
      });

      invariant(result.snapshot, "no snapshot");
      expect(result.snapshot.document.order).toEqual([CELL_1]);
      expect(cellIn(result, CELL_1)).toEqual({
        id: CELL_1,
        notebook_id: "embedded",
        name: "my_cell",
        code: "print('hello')",
        config: {
          hide_code: false,
          disabled: false,
          column: null,
          expand_output: false,
        },
        etag: `embedded:${CELL_1}`,
        code_hash: `embedded:${CELL_1}:code`,
        version: 1,
      });
    });

    it("creates state from notebook with custom config", () => {
      const notebook = createNotebook([
        createNotebookCell("cell-1", {
          code: "code",
          name: "name",
          config: {
            hide_code: true,
            disabled: true,
            column: 1,
            expand_output: true,
          },
        }),
      ]);
      const result = readExport({
        session: null,
        notebook: notebook,
        filename: null,
        appConfig: {},
      });

      invariant(result.snapshot, "no snapshot");
      expect(cellIn(result, CELL_1).config).toEqual({
        hide_code: true,
        disabled: true,
        column: 1,
        expand_output: true,
      });
    });

    it("handles null/undefined fields in notebook cell", () => {
      const notebookCell = {
        id: "cell-1",
        code: null,
        name: null,
        code_hash: null,
        config: {
          hide_code: null,
          disabled: null,
          column: null,
        },
      };
      const notebook = createNotebook([notebookCell]);
      const result = readExport({
        session: null,
        notebook: notebook,
        filename: null,
        appConfig: {},
      });

      invariant(result.snapshot, "no snapshot");
      expect(cellIn(result, CELL_1)).toEqual({
        id: CELL_1,
        notebook_id: "embedded",
        name: "_",
        code: null,
        config: {
          hide_code: false,
          disabled: false,
          column: null,
          expand_output: false,
        },
        etag: `embedded:${CELL_1}`,
        code_hash: `embedded:${CELL_1}:code`,
        version: 1,
      });
    });

    it("uses SETUP_CELL_ID for setup cell with null id", () => {
      const notebookCell = {
        id: null,
        code: "import marimo as mo",
        name: "setup",
        code_hash: null,
        config: {
          hide_code: null,
          disabled: null,
          column: null,
        },
      };
      const notebook = createNotebook([notebookCell as any]);
      const result = readExport({
        session: null,
        notebook: notebook,
        filename: null,
        appConfig: {},
      });

      invariant(result.snapshot, "no snapshot");
      expect(result.snapshot.document.order).toEqual([SETUP_CELL_ID]);
      expect(cellIn(result, SETUP_CELL_ID)).toEqual({
        id: SETUP_CELL_ID,
        notebook_id: "embedded",
        name: "setup",
        code: "import marimo as mo",
        config: {
          hide_code: false,
          disabled: false,
          column: null,
          expand_output: false,
        },
        etag: `embedded:${SETUP_CELL_ID}`,
        code_hash: `embedded:${SETUP_CELL_ID}:code`,
        version: 1,
      });
    });
  });

  describe("both session and notebook scenarios", () => {
    it("creates state when session and notebook have matching cells", () => {
      const session = createSession([
        createSessionCell(
          "cell-1",
          [],
          [
            {
              type: "stream",
              name: "stdout",
              text: "output",
              mimetype: "text/plain",
            },
          ],
        ),
      ]);
      const notebook = createNotebook([
        createNotebookCell("cell-1", {
          code: "print('hello')",
          name: "my_cell",
        }),
      ]);
      const result = readExport({
        session: session,
        notebook: notebook,
        filename: null,
        appConfig: {},
      });

      invariant(result.snapshot, "no snapshot");
      expect(cellIn(result, CELL_1)).toEqual({
        id: CELL_1,
        notebook_id: "embedded",
        name: "my_cell",
        code: "print('hello')",
        config: {
          hide_code: false,
          disabled: false,
          column: null,
          expand_output: false,
        },
        etag: `embedded:${CELL_1}`,
        code_hash: `embedded:${CELL_1}:code`,
        version: 1,
      });
      // Null result means no output.
      expect(result.cellRuntime[CELL_1].consoleOutputs).toEqual([]);
    });

    it("creates state when cell order differs but same cells", () => {
      const session = createSession([
        createSessionCell("cell-1"),
        createSessionCell("cell-2"),
      ]);
      const notebook = createNotebook([
        createNotebookCell("cell-2", {}),
        createNotebookCell("cell-1", {}),
      ]);

      const result = readExport({
        session: session,
        notebook: notebook,
        filename: null,
        appConfig: {},
      });

      invariant(result.snapshot, "no snapshot");
      expect(result.snapshot.document.order).toEqual(["cell-2", "cell-1"]);
    });

    it("creates state when session and notebook have identical cell arrays", () => {
      const session = createSession([
        createSessionCell("cell-1"),
        createSessionCell("cell-2"),
      ]);
      const notebook = createNotebook([
        createNotebookCell("cell-1", {}),
        createNotebookCell("cell-2", {}),
      ]);

      const result = readExport({
        session: session,
        notebook: notebook,
        filename: null,
        appConfig: {},
      });

      expect(Logger.error).not.toHaveBeenCalled();
      invariant(result.snapshot, "no snapshot");
      expect(result.snapshot.document.order).toEqual(["cell-1", "cell-2"]);
    });
  });

  describe("empty cells scenarios", () => {
    it("warns and returns null when session has empty cells array", () => {
      const session = createSession([]);
      const result = readExport({
        session: session,
        notebook: null,
        filename: null,
        appConfig: {},
      });

      expect(result.snapshot).toBeNull();
    });

    it("warns and returns null when notebook has empty cells array", () => {
      const notebook = createNotebook([]);
      const result = readExport({
        session: null,
        notebook: notebook,
        filename: null,
        appConfig: {},
      });

      expect(result.snapshot).toBeNull();
    });

    it("warns and returns null when both have empty cells arrays", () => {
      const session = createSession([]);
      const notebook = createNotebook([]);
      const result = readExport({
        session: session,
        notebook: notebook,
        filename: null,
        appConfig: {},
      });

      expect(result.snapshot).toBeNull();
    });
  });

  describe("edge cases", () => {
    it("handles session cell with no outputs", () => {
      const session = createSession([createSessionCell("cell-1", [])]);
      const result = readExport({
        session: session,
        notebook: null,
        filename: null,
        appConfig: {},
      });

      invariant(result.snapshot, "no snapshot");
      expect(result.cellRuntime[CELL_1].output).toBeNull();
      expect(result.cellRuntime[CELL_1].consoleOutputs).toEqual([]);
      expect(result.cellRuntime[CELL_1].outline).toBeNull();
    });

    it("handles session cell with empty console array", () => {
      const session = createSession([createSessionCell("cell-1", [], [])]);
      const result = readExport({
        session: session,
        notebook: null,
        filename: null,
        appConfig: {},
      });

      invariant(result.snapshot, "no snapshot");
      expect(result.cellRuntime[CELL_1].consoleOutputs).toEqual([]);
    });

    it("handles session cell with multiple outputs (uses first one)", () => {
      const outputs = [
        { type: "data" as const, data: { "text/plain": "First" } },
        { type: "data" as const, data: { "text/plain": "Second" } },
      ];
      const session = createSession([createSessionCell("cell-1", outputs)]);
      const result = readExport({
        session: session,
        notebook: null,
        filename: null,
        appConfig: {},
      });

      invariant(result.snapshot, "no snapshot");
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
      const result = readExport({
        session: session,
        notebook: null,
        filename: null,
        appConfig: {},
      });

      invariant(result.snapshot, "no snapshot");
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
      const result = readExport({
        session: session,
        notebook: null,
        filename: null,
        appConfig: {},
      });

      invariant(result.snapshot, "no snapshot");
      expect(result.cellRuntime[CELL_1].output).toEqual({
        channel: "output",
        data: undefined,
        mimetype: undefined,
        timestamp: 0,
      });
    });

    it("returns correct structure with all expected properties", () => {
      const session = createSession([createSessionCell("cell-1")]);
      const result = readExport({
        session: session,
        notebook: null,
        filename: null,
        appConfig: {},
      });

      invariant(result.snapshot, "no snapshot");
      expect(result.snapshot.notebook).toEqual({
        id: "embedded",
        project_id: "embedded",
        path: null,
        name: "",
        updated_at: null,
      });
      expect(result.snapshot.document).toMatchObject({
        notebook_id: "embedded",
        order: result.snapshot.cells.map((cell) => cell.id),
        version: 1,
      });
      expect(Object.keys(result.cellRuntime)).toEqual(
        result.snapshot.document.order,
      );
    });
  });

  describe("session and notebook merge with code values abcdef", () => {
    it("merges session and notebook with code values a-f and correct hashes", () => {
      // md5 hashes for 'a' through 'f'
      const hashes = {
        a: "0cc175b9c0f1b6a831c399e269772661",
        b: "92eb5ffee6ae2fec3ad71c777531578f",
        c: "4a8a08f09d37b73795649038408b5f33",
        d: "8277e0910d750195b448797616e091ad",
        e: "e1671797c52e15f763380b45e841ec32",
        f: "8fa14cdd754f91cc6554c9e71929cce7",
      };
      // Create notebook cells with code values 'a' through 'f'
      const notebookCells = [
        createNotebookCell("cell-a", {
          code: "a",
          name: null,
          config: null,
          code_hash: hashes.a,
        }),
        createNotebookCell("cell-b", {
          code: "b",
          name: null,
          config: null,
          code_hash: hashes.b,
        }),
        createNotebookCell("cell-c", {
          code: "c",
          name: null,
          config: null,
          code_hash: hashes.c,
        }),
        createNotebookCell("cell-d", {
          code: "d",
          name: null,
          config: null,
          code_hash: hashes.d,
        }),
        createNotebookCell("cell-e", {
          code: "e",
          name: null,
          config: null,
          code_hash: hashes.e,
        }),
        createNotebookCell("cell-f", {
          code: "f",
          name: null,
          config: null,
          code_hash: hashes.f,
        }),
      ];
      // Create session cells with matching code_hashes
      const sessionCells = [
        createSessionCell(
          "cell-a",
          [{ type: "data", data: { "text/plain": "A!" } }],
          [],
          hashes.a,
        ),
        createSessionCell(
          "cell-b",
          [{ type: "data", data: { "text/plain": "B!" } }],
          [],
          hashes.b,
        ),
        createSessionCell(
          "cell-c",
          [{ type: "data", data: { "text/plain": "C!" } }],
          [],
          hashes.c,
        ),
        createSessionCell(
          "cell-d",
          [{ type: "data", data: { "text/plain": "D!" } }],
          [],
          hashes.d,
        ),
        createSessionCell(
          "cell-e",
          [{ type: "data", data: { "text/plain": "E!" } }],
          [],
          hashes.e,
        ),
        createSessionCell(
          "cell-f",
          [{ type: "data", data: { "text/plain": "F!" } }],
          [],
          hashes.f,
        ),
      ];
      const session = createSession(sessionCells);
      const notebook = createNotebook(notebookCells);
      const result = readExport({
        session: session,
        notebook: notebook,
        filename: null,
        appConfig: {},
      });
      invariant(result.snapshot, "no snapshot");
      // Should have all cell IDs in order
      expect(result.snapshot.document.order).toEqual([
        "cell-a",
        "cell-b",
        "cell-c",
        "cell-d",
        "cell-e",
        "cell-f",
      ]);
      // Should have correct code and output for each cell
      for (const code of ["a", "b", "c", "d", "e", "f"]) {
        const cid = cellId(`cell-${code}`);
        expect(cellIn(result, cid).code).toBe(code);
        expect(result.cellRuntime[cid].output).toEqual({
          channel: "output",
          data: `${code.toUpperCase()}!`,
          mimetype: "text/plain",
          timestamp: 0,
        });
      }
    });

    it("merges session and notebook with abcde -> aczeg edit distance scenario", () => {
      // md5 hashes for the codes
      const hashes = {
        a: "0cc175b9c0f1b6a831c399e269772661",
        b: "92eb5ffee6ae2fec3ad71c777531578f",
        c: "4a8a08f09d37b73795649038408b5f33",
        d: "8277e0910d750195b448797616e091ad",
        e: "e1671797c52e15f763380b45e841ec32",
        z: "fbade9e36a3f36d3d676c1b808451dd7", // hash for 'z'
        g: "b2f5ff47436671b6e533d8dc3614845d", // hash for 'g'
      };

      // Session has cells with code 'a', 'b', 'c', 'd', 'e'
      const sessionCells = [
        createSessionCell(
          "cell-a",
          [{ type: "data", data: { "text/plain": "A!" } }],
          [],
          hashes.a,
        ),
        createSessionCell(
          "cell-b",
          [{ type: "data", data: { "text/plain": "B!" } }],
          [],
          hashes.b,
        ),
        createSessionCell(
          "cell-c",
          [{ type: "data", data: { "text/plain": "C!" } }],
          [],
          hashes.c,
        ),
        createSessionCell(
          "cell-d",
          [{ type: "data", data: { "text/plain": "D!" } }],
          [],
          hashes.d,
        ),
        createSessionCell(
          "cell-e",
          [{ type: "data", data: { "text/plain": "E!" } }],
          [],
          hashes.e,
        ),
      ];

      // Notebook has cells with code 'a', 'c', 'z', 'e', 'g'
      const notebookCells = [
        createNotebookCell("cell-a", {
          code: "a",
          name: null,
          config: null,
          code_hash: hashes.a,
        }),
        createNotebookCell("cell-c", {
          code: "c",
          name: null,
          config: null,
          code_hash: hashes.c,
        }),
        createNotebookCell("cell-z", {
          code: "z",
          name: null,
          config: null,
          code_hash: hashes.z,
        }),
        createNotebookCell("cell-e", {
          code: "e",
          name: null,
          config: null,
          code_hash: hashes.e,
        }),
        createNotebookCell("cell-g", {
          code: "g",
          name: null,
          config: null,
          code_hash: hashes.g,
        }),
      ];

      const session = createSession(sessionCells);
      const notebook = createNotebook(notebookCells);
      const result = readExport({
        session: session,
        notebook: notebook,
        filename: null,
        appConfig: {},
      });

      invariant(result.snapshot, "no snapshot");

      // Should have notebook cell IDs in order (notebook is canonical)
      expect(result.snapshot.document.order).toEqual([
        "cell-a",
        "cell-c",
        "cell-z",
        "cell-e",
        "cell-g",
      ]);

      // Should have correct code for each cell
      expect(cellIn(result, "cell-a").code).toBe("a");
      expect(cellIn(result, "cell-c").code).toBe("c");
      expect(cellIn(result, "cell-z").code).toBe("z");
      expect(cellIn(result, "cell-e").code).toBe("e");
      expect(cellIn(result, "cell-g").code).toBe("g");

      // Should have session outputs for matching cells (a, c, e)
      expect(result.cellRuntime[cellId("cell-a")].output).toEqual({
        channel: "output",
        data: "A!",
        mimetype: "text/plain",
        timestamp: 0,
      });
      expect(result.cellRuntime[cellId("cell-c")].output).toEqual({
        channel: "output",
        data: "C!",
        mimetype: "text/plain",
        timestamp: 0,
      });
      expect(result.cellRuntime[cellId("cell-e")].output).toEqual({
        channel: "output",
        data: "E!",
        mimetype: "text/plain",
        timestamp: 0,
      });

      // Should have no output for new cells (z, g) - they get stub session cells
      expect(result.cellRuntime[cellId("cell-z")].output).toBeNull();
      expect(result.cellRuntime[cellId("cell-g")].output).toBeNull();

      // Should log warning about different cells
      expect(Logger.warn).toHaveBeenCalledWith(
        "Session and notebook have different cells, attempted merge.",
      );
    });

    it("merges session and notebook with mismatched cells and swapped code hashes", () => {
      // This test simulates a real-world scenario where:
      // - Session has cells cell-999, cell-1, cell-2 with certain outputs
      // - Notebook has cells cell-1, cell-2, cell-3 with different code
      // - The code hashes are mismatched, showing code has changed
      //
      // The merge algorithm uses edit distance on code hashes to match cells:
      // - Session cell-1 (hash=moMd) matches Notebook cell-2 (hash=moMd)
      // - Session cell-2 (hash=slider) matches Notebook cell-3 (hash=slider)
      // - Session cell-999 (hash=null) doesn't match anything (null hashes never match)
      // - Notebook cell-1 (hash=null) gets a stub session cell
      const hashes = {
        moMd: "2260380a88f9b8759c0ccb1230f1498e", // hash for mo.md("Hello")
        slider: "34938d98b7a6c88431d6cad23ea0a574", // hash for x = mo.ui.slider(0, 10)
      };

      // Session has cells: cell-999 (error, no hash), cell-1 (markdown, hash=moMd), cell-2 (empty, hash=slider)
      const sessionCells = [
        createSessionCell(
          "cell-999",
          [
            {
              type: "error",
              ename: "exception",
              evalue: "division by zero",
              traceback: [],
            },
          ],
          [
            {
              type: "stream",
              name: "stderr",
              text: "Traceback (most recent call last): File <stdin>, line 1, in <module ZeroDivisionError: division by zero",
              mimetype: "application/vnd.marimo+traceback",
            },
          ],
          null, // no hash - won't match anything
        ),
        createSessionCell(
          "cell-1",
          [
            {
              type: "data",
              data: { "text/markdown": "Welcome to marimo!" },
            },
          ],
          [],
          hashes.moMd, // matches notebook cell-2
        ),
        createSessionCell(
          "cell-2",
          [
            {
              type: "data",
              data: { "text/plain": "" },
            },
          ],
          [],
          hashes.slider, // matches notebook cell-3
        ),
      ];

      // Notebook has cells: cell-1 (1 / 0, no hash), cell-2 (mo.md("Hello"), hash=moMd), cell-3 (slider, hash=slider)
      const notebookCells = [
        createNotebookCell("cell-1", {
          code: "1 / 0",
          name: null,
          config: null,
          code_hash: null,
        }), // no hash
        createNotebookCell("cell-2", {
          code: 'mo.md("Hello")',
          name: null,
          config: null,
          code_hash: hashes.moMd,
        }),
        createNotebookCell("cell-3", {
          code: "x = mo.ui.slider(0, 10)",
          name: null,
          config: null,
          code_hash: hashes.slider,
        }),
      ];

      const session = createSession(sessionCells);
      const notebook = createNotebook(notebookCells);
      const result = readExport({
        session: session,
        notebook: notebook,
        filename: null,
        appConfig: {},
      });

      invariant(result.snapshot, "no snapshot");

      // Should have notebook cell IDs in order (notebook is canonical)
      expect(result.snapshot.document.order).toEqual([
        "cell-1",
        "cell-2",
        "cell-3",
      ]);

      // Should have correct code from notebook
      expect(cellIn(result, "cell-1").code).toBe("1 / 0");
      expect(cellIn(result, "cell-2").code).toBe('mo.md("Hello")');
      expect(cellIn(result, "cell-3").code).toBe("x = mo.ui.slider(0, 10)");

      // cell-1: No matching session cell (hash is null), gets stub session cell
      expect(result.cellRuntime[cellId("cell-1")].output).toBeNull();
      expect(result.cellRuntime[cellId("cell-1")].consoleOutputs).toEqual([]);

      // cell-2: Matches session cell-1 by hash (moMd), gets its output
      expect(result.cellRuntime[cellId("cell-2")].output).toEqual({
        channel: "output",
        data: "Welcome to marimo!",
        mimetype: "text/markdown",
        timestamp: 0,
      });

      // cell-3: Matches session cell-2 by hash (slider), gets its output
      expect(result.cellRuntime[cellId("cell-3")].output).toEqual({
        channel: "output",
        data: "",
        mimetype: "text/plain",
        timestamp: 0,
      });

      // Should log warning about different cells (merge had edit distance > 0)
      expect(Logger.warn).toHaveBeenCalledWith(
        "Session and notebook have different cells, attempted merge.",
      );
    });
  });
});
