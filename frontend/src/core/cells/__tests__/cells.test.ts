/* Copyright 2026 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { createStore } from "jotai";
import { createRef } from "react";
import {
  afterAll,
  beforeAll,
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import type { CellHandle } from "@/components/editor/notebook-cell";
import { CellId } from "@/core/cells/ids";
import { foldAllBulk, unfoldAllBulk } from "@/core/codemirror/editing/commands";
import { adaptiveLanguageConfiguration } from "@/core/codemirror/language/extension";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import type { OutputMessage } from "@/core/kernel/messages";
import type { CellConfig } from "@/core/network/types";
import {
  type CollapsibleTree,
  MultiColumn,
  type CellColumnId,
} from "@/utils/id-tree";
import type { Seconds } from "@/utils/time";
import {
  exportedForTesting,
  flattenTopLevelNotebookCells,
  type NotebookState,
  notebookAtom,
} from "../cells";
import {
  type CellData,
  createCell,
  createCellConfig,
  createCellRuntimeState,
} from "../types";

vi.mock("@/core/codemirror/editing/commands", () => ({
  foldAllBulk: vi.fn(),
  unfoldAllBulk: vi.fn(),
}));
vi.mock("@/core/wasm/utils", () => ({
  isWasm: vi.fn(() => false),
}));
vi.mock("../scrollCellIntoView", async (importOriginal) => {
  const actual = await importOriginal();
  return {
    // oxlint-disable-next-line typescript/no-explicit-any
    ...(actual as any),
    scrollToTop: vi.fn(),
    scrollToBottom: vi.fn(),
    focusAndScrollCellIntoView: vi.fn(),
  };
});

const FIRST_COLUMN = 0;

const { initialNotebookState, reducer, createActions } = exportedForTesting;

function formatCells(notebook: NotebookState) {
  const { cellIds, cellData } = notebook;
  const wrap = (text: string) => {
    return `\n${text}\n`;
  };

  const printCell = (cell: CellData) => {
    return `[${cell.id}] '${cell.code}'`;
  };
  const printCells = (cellsId: CellId[]) => {
    const cells = cellsId.map((cellId) => cellData[cellId]);
    return cells.map((cell) => printCell(cell)).join("\n\n");
  };
  const printColumn = (column: CollapsibleTree<CellId>, columnIdx: number) => {
    return `> col ${columnIdx}\n${printCells(column.inOrderIds)}`;
  };
  const columns = cellIds.getColumns();
  if (columns.length > 1) {
    return wrap(columns.map(printColumn).join("\n\n"));
  }
  return wrap(printCells(cellIds.inOrderIds));
}

function createEditor(content: string) {
  const state = EditorState.create({
    doc: content,
    extensions: [
      python(),
      adaptiveLanguageConfiguration({
        cellId: cellId("cell1"),
        completionConfig: {
          activate_on_typing: true,
          signature_hint_on_typing: false,
          copilot: false,
          codeium_api_key: null,
        },
        hotkeys: new OverridingHotkeyProvider({}),
        placeholderType: "marimo-import",
        lspConfig: {},
      }),
    ],
  });

  const view = new EditorView({
    state,
    parent: document.body,
  });

  return view;
}

describe("cell reducer", () => {
  let state: NotebookState;
  let cells: ReturnType<typeof flattenTopLevelNotebookCells>;
  let firstCellId: CellId;

  const mountEditors = () => {
    for (const [cellIdString, handle] of Object.entries(state.cellHandles)) {
      // @ts-expect-error - Typescript Object.entries doesn't know that keys are CellId
      const cid: CellId = cellIdString;
      if (!handle.current) {
        const view = createEditor(state.cellData[cid].code);
        const handle: CellHandle = {
          editorView: view,
          editorViewOrNull: view,
        };
        state.cellHandles[cid] = { current: handle };
      }
    }
    cells = flattenTopLevelNotebookCells(state);
  };
  const actions = createActions((action) => {
    state = reducer(state, action);
    mountEditors();
  });

  /** Put a cell into the notebook the way the document would. */
  function seedCell({
    cellId,
    before,
    code = "",
    name,
    config,
    newCellId,
    hideCode,
    autoFocus = true,
  }: {
    cellId: CellId | "__end__" | { type: "__end__"; columnId: CellColumnId };
    before: boolean;
    code?: string;
    name?: string;
    config?: CellConfig;
    newCellId?: CellId;
    hideCode?: boolean;
    autoFocus?: boolean;
  }): CellId {
    let column: CollapsibleTree<CellId>;
    let cellIndex: number;
    if (cellId === "__end__") {
      column = state.cellIds.atOrThrow(0);
      cellIndex = column.length;
    } else if (typeof cellId === "string") {
      column = state.cellIds.findWithId(cellId);
      cellIndex = column.topLevelIds.indexOf(cellId);
    } else {
      column = state.cellIds.get(cellId.columnId) ?? state.cellIds.atOrThrow(0);
      cellIndex = column.length;
    }
    const id = newCellId ?? CellId.create();
    state = {
      ...state,
      cellIds: state.cellIds.insertId(
        id,
        column.id,
        before ? cellIndex : cellIndex + 1,
      ),
      cellData: {
        ...state.cellData,
        [id]: createCell({
          id,
          code,
          name,
          config: createCellConfig({
            ...config,
            ...(hideCode != null && { hide_code: hideCode }),
          }),
          edited: Boolean(code),
        }),
      },
      cellRuntime: { ...state.cellRuntime, [id]: createCellRuntimeState() },
      cellHandles: { ...state.cellHandles, [id]: createRef() },
      scrollKey: autoFocus ? id : null,
    };
    mountEditors();
    return id;
  }

  let i = 0;
  const originalCreate = CellId.create.bind(CellId);

  beforeAll(() => {
    CellId.create = () => {
      return cellId(`${i++}`);
    };
  });

  beforeEach(() => {
    i = 0;

    state = initialNotebookState();
    state.cellIds = MultiColumn.from([]);
    seedCell({ cellId: "__end__", before: false });
    firstCellId = state.cellIds.inOrderIds[0];
  });

  afterAll(() => {
    CellId.create = originalCreate;
  });

  it("can update a cell", () => {
    actions.updateCellCode({
      cellId: firstCellId,
      code: "import numpy as np",
      formattingChange: false,
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [0] 'import numpy as np'
      "
    `);
  });

  it("keeps error evidence after an edit and a new queued run", () => {
    const code = "raise ValueError('old failure')";
    const output: OutputMessage = {
      channel: "marimo-error",
      mimetype: "application/vnd.marimo+error",
      data: [
        {
          type: "exception",
          msg: "old failure",
          exception_type: "ValueError",
          raising_cell: null,
          traceback: "<pre>ValueError: old failure</pre>",
        },
      ],
      code,
      timestamp: 1,
    };
    actions.handleCellMessage({
      cell_id: firstCellId,
      output,
      console: {
        channel: "stderr",
        mimetype: "application/vnd.marimo+traceback",
        data: "<pre>ValueError: old failure</pre>",
        code,
        timestamp: 1,
      },
      status: "idle",
      stale_inputs: null,
      timestamp: 1,
    });
    actions.updateCellCode({
      cellId: firstCellId,
      code: "print('new code')",
      formattingChange: false,
    });
    actions.prepareForRun({ cellId: firstCellId });
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: null,
      console: null,
      status: "queued",
      stale_inputs: null,
      timestamp: 2,
    });
    const runtime = state.cellRuntime[firstCellId];
    expect(state.cellData[firstCellId].lastCodeRun).toBe("print('new code')");
    expect(runtime.output).toEqual(output);
    expect(runtime.consoleOutputs[0].code).toBe(code);
    expect(runtime.consoleOutputs[0].data).toContain("old failure");
  });

  it("can run cell and receive cell messages", () => {
    // HAPPY PATH
    /////////////////
    // Initial state
    let cell = cells[0];
    expect(cell.status).toBe("idle");
    expect(cell.lastCodeRun).toBe(null);
    expect(cell.edited).toBe(false);
    expect(cell).toMatchSnapshot("initial state");

    // Update code
    actions.updateCellCode({
      cellId: firstCellId,
      code: "import marimo as mo",
      formattingChange: false,
    });
    cell = cells[0];
    expect(cell.status).toBe("idle");
    expect(cell.lastCodeRun).toBe(null);
    expect(cell.edited).toBe(true);
    expect(cell).toMatchSnapshot("code edited");

    // Prepare for run
    actions.prepareForRun({
      cellId: firstCellId,
    });
    cell = cells[0];
    expect(cell.status).toBe("queued");
    expect(cell.lastCodeRun).toBe("import marimo as mo");
    expect(cell.edited).toBe(false);
    expect(cell).toMatchSnapshot("prepared for run");

    // Receive queued messages
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: undefined,
      console: null,
      status: "queued",
      stale_inputs: null,
      timestamp: new Date(10).getTime() as Seconds,
    });
    cell = cells[0];
    expect(cell.status).toBe("queued");
    expect(cell.lastCodeRun).toBe("import marimo as mo");
    expect(cell.edited).toBe(false);
    expect(cell.runElapsedTimeMs).toBe(null);
    expect(cell.runStartTimestamp).toBe(null);
    expect(cell.lastRunStartTimestamp).toBe(null);
    expect(cell).toMatchSnapshot("queued message received");

    // Receive running messages
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: undefined,
      console: null,
      status: "running",
      stale_inputs: null,
      timestamp: new Date(20).getTime() as Seconds,
    });
    cell = cells[0];
    expect(cell.status).toBe("running");
    expect(cell.lastCodeRun).toBe("import marimo as mo");
    expect(cell.edited).toBe(false);
    expect(cell.runElapsedTimeMs).toBe(null);
    expect(cell.runStartTimestamp).toBe(20);
    expect(cell.lastRunStartTimestamp).toBe(20);
    expect(cell).toMatchSnapshot("running message received");

    // Console messages shouldn't transition status
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: undefined,
      console: {
        channel: "stdout",
        mimetype: "text/plain",
        data: "hello!",
        timestamp: 0,
      },
      status: undefined,
      stale_inputs: null,
      timestamp: new Date(22).getTime() as Seconds,
    });
    cell = cells[0];
    expect(cell.status).toBe("running");
    expect(cell.edited).toBe(false);
    expect(cell.runElapsedTimeMs).toBe(null);
    expect(cell.runStartTimestamp).toBe(20);
    expect(cell.lastRunStartTimestamp).toBe(20);
    expect(cell).toMatchSnapshot("console message received");

    // Receive output messages
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: {
        channel: "output",
        mimetype: "text/plain",
        data: "ok",
        timestamp: 0,
      },
      console: {
        channel: "stdout",
        mimetype: "text/plain",
        data: "hello!",
        timestamp: 0,
      },
      status: "idle",
      stale_inputs: null,
      timestamp: new Date(33).getTime() as Seconds,
    });
    cell = cells[0];
    expect(cell.status).toBe("idle");
    expect(cell.edited).toBe(false);
    expect(cell.runElapsedTimeMs).toBe(13_000);
    expect(cell.runStartTimestamp).toBe(null);
    expect(cell.lastRunStartTimestamp).toBe(20);
    expect(cell).toMatchSnapshot("output received");

    // EDITING BACK AND FORTH
    /////////////////
    // Update code again
    actions.updateCellCode({
      cellId: firstCellId,
      code: "import marimo as mo\nimport numpy",
      formattingChange: false,
    });
    cell = cells[0];
    expect(cell.status).toBe("idle");
    expect(cell.edited).toBe(true);
    expect(cell).toMatchSnapshot("code edited again");

    // Update code should be unedited
    actions.updateCellCode({
      cellId: firstCellId,
      code: "import marimo as mo",
      formattingChange: false,
    });
    cell = cells[0];
    expect(cell.edited).toBe(false);
    expect(cell).toMatchSnapshot("code reverted");

    // Update code should be edited again
    actions.updateCellCode({
      cellId: firstCellId,
      code: "import marimo as mo\nimport numpy",
      formattingChange: false,
    });
    cell = cells[0];
    expect(cell.status).toBe("idle");
    expect(cell.lastCodeRun).toBe("import marimo as mo");
    expect(cell.edited).toBe(true);
    expect(cell).toMatchSnapshot("code changed after revert");

    // ERROR RESPONSE
    /////////////////
    // Prepare for run
    actions.prepareForRun({
      cellId: firstCellId,
    });
    cell = cells[0];
    expect(cell.output).not.toBe(null); // keep old output
    // Queue
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: undefined,
      console: null,
      status: "queued",
      stale_inputs: null,
      timestamp: new Date(40).getTime() as Seconds,
    });
    cell = cells[0];
    expect(cell.output).not.toBe(null); // keep old output
    // Running
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: undefined,
      console: null,
      status: "running",
      stale_inputs: null,
      timestamp: new Date(50).getTime() as Seconds,
    });
    cell = cells[0];
    expect(cell.output).not.toBe(null); // keep old output
    // Receive error
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: {
        channel: "marimo-error",
        mimetype: "application/vnd.marimo+error",
        data: [
          { type: "exception", exception_type: "ValueError", msg: "Oh no!" },
        ],
        timestamp: 0,
      },
      console: null,
      status: "idle",
      stale_inputs: null,
      timestamp: new Date(61).getTime() as Seconds,
    });
    cell = cells[0];
    expect(cell.output).not.toBe(null); // keep old output
    expect(cell.status).toBe("idle");
    expect(cell.lastCodeRun).toBe("import marimo as mo\nimport numpy");
    expect(cell.edited).toBe(false);
    expect(cell.runElapsedTimeMs).toBe(11_000);
    expect(cell.runStartTimestamp).toBe(null);
    expect(cell).toMatchSnapshot("error response received");

    // INTERRUPT RESPONSE
    /////////////////
    // Prepare for run
    actions.prepareForRun({
      cellId: firstCellId,
    });
    cell = cells[0];
    expect(cell.output).not.toBe(null); // keep old output
    // Queue
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: undefined,
      console: null,
      status: "queued",
      stale_inputs: null,
      timestamp: new Date(40).getTime() as Seconds,
    });
    cell = cells[0];
    expect(cell.output).not.toBe(null); // keep old output
    // Running
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: undefined,
      console: null,
      status: "running",
      stale_inputs: null,
      timestamp: new Date(50).getTime() as Seconds,
    });
    cell = cells[0];
    expect(cell.output).not.toBe(null); // keep old output
    // Receive error
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: {
        channel: "marimo-error",
        mimetype: "application/vnd.marimo+error",
        data: [{ type: "interruption" }],
        timestamp: 0,
      },
      console: null,
      status: "idle",
      stale_inputs: null,
      timestamp: new Date(61).getTime() as Seconds,
    });
    cell = cells[0];
    expect(cell.status).toBe("idle");
    expect(cell.lastCodeRun).toBe(cell.code);
    expect(cell.edited).toBe(false);
    expect(cell.runElapsedTimeMs).toBe(11_000);
    expect(cell.runStartTimestamp).toBe(null);
    expect(cell).toMatchSnapshot("interruption response received");
  });

  it("errors reset status to idle", () => {
    // Initial state
    let cell = cells[0];
    expect(cell.status).toBe("idle");
    expect(cell.lastCodeRun).toBe(null);
    expect(cell.edited).toBe(false);
    expect(cell).toMatchSnapshot("initial state");

    // Update code
    actions.updateCellCode({
      cellId: firstCellId,
      code: "import marimo as mo",
      formattingChange: false,
    });
    cell = cells[0];
    expect(cell.status).toBe("idle");
    expect(cell.lastCodeRun).toBe(null);
    expect(cell.edited).toBe(true);
    expect(cell).toMatchSnapshot("code edited");

    // Prepare for run
    actions.prepareForRun({
      cellId: firstCellId,
    });
    cell = cells[0];
    expect(cell.status).toBe("queued");
    expect(cell.lastCodeRun).toBe("import marimo as mo");
    expect(cell.edited).toBe(false);
    expect(cell).toMatchSnapshot("prepared for run");

    // ERROR RESPONSE
    //
    // should reset status to idle
    /////////////////
    // Prepare for run
    actions.prepareForRun({
      cellId: firstCellId,
    });
    cell = cells[0];
    // Receive error
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: {
        channel: "marimo-error",
        mimetype: "application/vnd.marimo+error",
        data: [
          { type: "exception", exception_type: "SyntaxError", msg: "Oh no!" },
        ],
        timestamp: 0,
      },
      console: null,
      stale_inputs: null,
      timestamp: new Date(61).getTime() as Seconds,
    });
    cell = cells[0];
    expect(cell.status).toBe("idle");
    expect(cell.lastCodeRun).toBe("import marimo as mo");
    expect(cell.edited).toBe(false);
    expect(cell.runElapsedTimeMs).toBe(null);
    expect(cell.runStartTimestamp).toBe(null);
    expect(cell).toMatchSnapshot("error response received");
  });

  it("can run a stale cell", () => {
    // Update code of first cell
    actions.updateCellCode({
      cellId: firstCellId,
      code: "import marimo as mo",
      formattingChange: false,
    });
    // Add cell
    seedCell({
      cellId: firstCellId,
      before: false,
    });
    const secondCell = cells[1].id;
    // Update code
    actions.updateCellCode({
      code: "mo.slider()",
      cellId: secondCell,
      formattingChange: false,
    });

    // Prepare for run
    actions.prepareForRun({
      cellId: secondCell,
    });

    // Receive queued messages
    actions.handleCellMessage({
      cell_id: secondCell,
      output: undefined,
      console: null,
      status: "queued",
      stale_inputs: null,
      timestamp: new Date(10).getTime() as Seconds,
    });
    let cell = cells[1];
    expect(cell.status).toBe("queued");
    expect(cell.lastCodeRun).toBe("mo.slider()");
    expect(cell.edited).toBe(false);
    expect(cell.runElapsedTimeMs).toBe(null);
    expect(cell.runStartTimestamp).toBe(null);
    expect(cell).toMatchSnapshot("queued message received");

    // Receive stale message
    actions.handleCellMessage({
      cell_id: secondCell,
      output: undefined,
      console: null,
      status: undefined,
      stale_inputs: true,
      timestamp: new Date(20).getTime() as Seconds,
    });
    cell = cells[1];
    expect(cell.status).toBe("queued");
    expect(cell.lastCodeRun).toBe("mo.slider()");
    expect(cell.edited).toBe(false);
    expect(cell.runElapsedTimeMs).toBe(null);
    expect(cell.runStartTimestamp).toBe(null);
    expect(cell).toMatchSnapshot("stale inputs received");
  });

  it("can format code and update cell", () => {
    const firstCellId = cells[0].id;
    actions.updateCellCode({
      cellId: firstCellId,
      code: "import marimo as    mo",
      formattingChange: false,
    });
    let cell = cells[0];
    expect(cell.status).toBe("idle");
    expect(cell.lastCodeRun).toBe(null);
    expect(cell.edited).toBe(true);

    // Run
    actions.prepareForRun({
      cellId: firstCellId,
    });
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: {
        channel: "output",
        mimetype: "text/plain",
        data: "ok",
        timestamp: 0,
      },
      console: {
        channel: "stdout",
        mimetype: "text/plain",
        data: "hello!",
        timestamp: 0,
      },
      status: "idle",
      stale_inputs: null,
      timestamp: new Date(33).getTime() as Seconds,
    });

    // Check steady state
    cell = cells[0];
    expect(cell.status).toBe("idle");
    expect(cell.edited).toBe(false);
    expect(cell.lastCodeRun).toBe("import marimo as    mo");

    // Format code
    actions.updateCellCode({
      cellId: firstCellId,
      code: "import marimo as mo",
      formattingChange: true,
    });
    cell = cells[0];
    expect(cell.status).toBe("idle");
    expect(cell.lastCodeRun).toBe("import marimo as mo");
    expect(cell.edited).toBe(false);
  });

  it("can run a stopped cell", () => {
    // Update code of first cell
    actions.updateCellCode({
      cellId: firstCellId,
      code: "mo.md('This has an ancestor that was stopped')",
      formattingChange: false,
    });

    // Prepare for run
    actions.prepareForRun({
      cellId: firstCellId,
    });

    // Receive queued messages
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: undefined,
      console: null,
      status: "queued",
      stale_inputs: null,
      timestamp: new Date(10).getTime() as Seconds,
    });
    let cell = cells[0];
    expect(cell.status).toBe("queued");
    expect(cell.lastCodeRun).toBe(
      "mo.md('This has an ancestor that was stopped')",
    );
    expect(cell.edited).toBe(false);
    expect(cell.runElapsedTimeMs).toBe(null);
    expect(cell.runStartTimestamp).toBe(null);
    expect(cell).toMatchSnapshot("queued message received");

    // Receive idle message
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: undefined,
      console: null,
      status: "idle",
      stale_inputs: null,
      timestamp: new Date(20).getTime() as Seconds,
    });
    cell = cells[0];
    expect(cell).toMatchSnapshot("idle message received");

    // Receive stop output
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: {
        channel: "marimo-error",
        mimetype: "application/vnd.marimo+error",
        data: [
          {
            msg: "This cell wasn't run because an ancestor was stopped with `mo.stop`: ",
            raising_cell: "2",
            type: "ancestor-stopped",
          },
        ],
        timestamp: new Date(20).getTime() as Seconds,
      },
      console: null,
      status: "idle",
      stale_inputs: null,
      timestamp: new Date(20).getTime() as Seconds,
    });
    cell = cells[0];
    expect(cell.status).toBe("idle");
    // oxlint-disable-next-line typescript/no-explicit-any no-unsafe-optional-chaining
    expect((cell.output?.data as any)[0].msg).toBe(
      "This cell wasn't run because an ancestor was stopped with `mo.stop`: ",
    );
    expect(cell.stopped).toBe(true);
    expect(cell).toMatchSnapshot("ancestor stopped");

    // Receive queued message
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: undefined,
      console: null,
      status: "queued",
      stale_inputs: null,
      timestamp: new Date(30).getTime() as Seconds,
    });
    cell = cells[0];
    expect(cell.status).toBe("queued");
    expect(cell.stopped).toBe(true);
    expect(cell).toMatchSnapshot("queued after stop");

    // Receive running message
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: undefined,
      console: null,
      status: "running",
      stale_inputs: null,
      timestamp: new Date(40).getTime() as Seconds,
    });
    cell = cells[0];
    expect(cell.status).toBe("running");
    expect(cell.stopped).toBe(false);
    expect(cell.output).toBe(null);
    expect(cell).toMatchSnapshot("running after stop");
  });

  it("can initialize stdin", () => {
    const STDOUT: OutputMessage = {
      channel: "stdout",
      mimetype: "text/plain",
      data: "hello!",
      timestamp: 1,
    };
    const STD_IN_1: OutputMessage = {
      channel: "stdin",
      mimetype: "text/plain",
      data: "what is your name?",
      timestamp: 2,
    };
    const STD_IN_2: OutputMessage = {
      channel: "stdin",
      mimetype: "text/plain",
      data: "how old are you?",
      timestamp: 3,
    };

    // Initial state
    let cell = cells[0];
    expect(cell.status).toBe("idle");
    expect(cell.consoleOutputs).toEqual([]);
    expect(cell).toMatchSnapshot("initial state");

    // Prepare for run
    actions.prepareForRun({
      cellId: firstCellId,
    });
    cell = cells[0];
    expect(cell.status).toBe("queued");
    expect(cell.consoleOutputs).toEqual([]);
    expect(cell).toMatchSnapshot("prepared for run");

    // Receive queued messages
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: undefined,
      console: null,
      status: "queued",
      stale_inputs: null,
      timestamp: new Date(10).getTime() as Seconds,
    });
    cell = cells[0];
    expect(cell.status).toBe("queued");
    expect(cell).toMatchSnapshot("queued message received");

    // Receive running messages
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: undefined,
      console: null,
      status: "running",
      stale_inputs: null,
      timestamp: new Date(20).getTime() as Seconds,
    });
    cell = cells[0];
    expect(cell.status).toBe("running");
    expect(cell).toMatchSnapshot("running message received");

    // Add console
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: undefined,
      console: STDOUT,
      status: undefined,
      stale_inputs: null,
      timestamp: new Date(22).getTime() as Seconds,
    });
    cell = cells[0];
    expect(cell.status).toBe("running");
    expect(cell).toMatchSnapshot("stdout received");

    cell = cells[0];
    expect(cell.consoleOutputs[0]).toMatchObject(STDOUT);
    expect(cell.status).toBe("running");
    expect(cell).toMatchSnapshot("stdout verified");

    // Ask via stdin
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: undefined,
      console: STD_IN_1,
      status: undefined,
      stale_inputs: null,
      timestamp: new Date(22).getTime() as Seconds,
    });
    cell = cells[0];
    expect(cell.consoleOutputs[0]).toMatchObject(STDOUT);
    expect(cell.consoleOutputs[1]).toMatchObject(STD_IN_1);
    expect(cell.status).toBe("running");
    expect(cell).toMatchSnapshot("stdin requested");

    // Response to stdin
    actions.setStdinResponse({
      response: "Marimo!",
      cellId: firstCellId,
      outputIndex: 1,
    });
    cell = cells[0];
    expect(cell.consoleOutputs[1]).toMatchObject({
      ...STD_IN_1,
      response: "Marimo!",
    });
    expect(cell.status).toBe("running");
    expect(cell).toMatchSnapshot("stdin answered");

    // Ask via stdin, again
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: undefined,
      console: STD_IN_2,
      status: undefined,
      stale_inputs: null,
      timestamp: new Date(22).getTime() as Seconds,
    });
    cell = cells[0];
    expect(cell.consoleOutputs).toMatchObject([
      STDOUT,
      { ...STD_IN_1, response: "Marimo!" },
      STD_IN_2,
    ]);
    expect(cell.status).toBe("running");
    expect(cell).toMatchSnapshot("second stdin requested");

    // Interrupt, so we respond with ""
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: {
        channel: "marimo-error",
        mimetype: "application/vnd.marimo+error",
        data: [{ type: "interruption" }],
        timestamp: 0,
      },
      console: null,
      status: "idle",
      stale_inputs: null,
      timestamp: new Date(61).getTime() as Seconds,
    });
    cell = cells[0];
    expect(cell.status).toBe("idle");
    expect(cell.consoleOutputs).toMatchObject([
      STDOUT,
      { ...STD_IN_1, response: "Marimo!" },
      { ...STD_IN_2, response: "" },
    ]);
  });

  it("resolves password prompts without retaining the response", () => {
    const prompt: OutputMessage = {
      channel: "stdin",
      mimetype: "text/password",
      data: "Password: ",
      timestamp: 1,
    };
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: undefined,
      console: prompt,
      status: "running",
      stale_inputs: null,
      timestamp: 1 as Seconds,
    });

    const secret = "getpass-regression-secret";
    actions.setStdinResponse({
      cellId: firstCellId,
      outputIndex: 0,
      response: secret,
    });

    expect(cells[0].consoleOutputs).toEqual([
      { ...prompt, id: 1, response: "" },
    ]);
    expect(JSON.stringify(cells[0].consoleOutputs)).not.toContain(secret);
  });

  it("does not crash when setStdinResponse has out-of-bounds outputIndex", () => {
    const STDOUT: OutputMessage = {
      channel: "stdout",
      mimetype: "text/plain",
      data: "hello!",
      timestamp: 1,
    };

    // Set the cell to running with a console output
    actions.prepareForRun({ cellId: firstCellId });
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: undefined,
      console: null,
      status: "running",
      stale_inputs: null,
      timestamp: new Date(20).getTime() as Seconds,
    });
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: undefined,
      console: STDOUT,
      status: undefined,
      stale_inputs: null,
      timestamp: new Date(22).getTime() as Seconds,
    });

    // Try to set stdin response with an out-of-bounds index
    // This should not crash - it should return state unchanged
    actions.setStdinResponse({
      response: "test",
      cellId: firstCellId,
      outputIndex: 999,
    });

    // Cell state should be unchanged
    const cell = cells[0];
    expect(cell.consoleOutputs).toHaveLength(1);
    expect(cell.consoleOutputs[0]).toMatchObject(STDOUT);
  });

  it("can receive console when the cell is idle and will clear when starts again", () => {
    const OLD_STDOUT: OutputMessage = {
      channel: "stdout",
      mimetype: "text/plain",
      data: "hello!",
      timestamp: 1,
    };
    const STDOUT: OutputMessage = {
      channel: "stdin",
      mimetype: "text/plain",
      data: "hello again!",
      timestamp: 2,
    };

    // Initial state
    let cell = cells[0];
    expect(cell.status).toBe("idle");
    expect(cell.consoleOutputs).toEqual([]);
    expect(cell).toMatchSnapshot("initial state");

    // Add console
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: undefined,
      console: [OLD_STDOUT],
      status: undefined,
      stale_inputs: null,
      timestamp: new Date(1).getTime() as Seconds,
    });

    // Prepare for run
    actions.prepareForRun({
      cellId: firstCellId,
    });
    cell = cells[0];
    expect(cell.status).toBe("queued");
    expect(cell.consoleOutputs).toMatchObject([OLD_STDOUT]); // Old stays there until it starts running
    expect(cell).toMatchSnapshot("prepared for run");

    // Receive queued messages
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: undefined,
      console: null,
      status: "queued",
      stale_inputs: null,
      timestamp: new Date(10).getTime() as Seconds,
    });
    cell = cells[0];
    expect(cell.status).toBe("queued");
    expect(cell.consoleOutputs).toMatchObject([OLD_STDOUT]); // Old stays there until it starts running
    expect(cell).toMatchSnapshot("queued message received");

    // Receive running messages
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: undefined,
      console: [], // Backend sends an empty array to clearu
      status: "running",
      stale_inputs: null,
      timestamp: new Date(20).getTime() as Seconds,
    });
    cell = cells[0];
    expect(cell.status).toBe("running");
    expect(cell.consoleOutputs).toMatchObject([]);
    expect(cell).toMatchSnapshot("console cleared while running");

    // Add console
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: undefined,
      console: [STDOUT],
      status: "idle",
      stale_inputs: null,
      timestamp: new Date(22).getTime() as Seconds,
    });
    cell = cells[0];
    expect(cell.consoleOutputs).toMatchObject([STDOUT]);
    expect(cell.status).toBe("idle");
    expect(cell).toMatchSnapshot("console received while idle");
  });

  it("can fold and unfold all cells", () => {
    actions.foldAll();
    expect(foldAllBulk).toHaveBeenCalled();

    actions.unfoldAll();
    expect(unfoldAllBulk).toHaveBeenCalled();
  });

  it("can clear logs", () => {
    state.cellLogs = [
      {
        level: "stderr",
        message: "log1",
        timestamp: 0,
        source: { type: "cell", cellId: firstCellId },
      },
      {
        level: "stderr",
        message: "log1",
        timestamp: 0,
        source: { type: "cell", cellId: firstCellId },
      },
    ];
    actions.clearLogs();
    expect(state.cellLogs).toEqual([]);
  });

  it("can handle multiple console outputs", () => {
    const STDOUT1: OutputMessage = {
      channel: "stdout",
      mimetype: "text/plain",
      data: "output1",
      timestamp: 1,
    };
    const STDOUT2: OutputMessage = {
      channel: "stdout",
      mimetype: "text/plain",
      data: "output2",
      timestamp: 2,
    };

    actions.handleCellMessage({
      cell_id: firstCellId,
      output: undefined,
      console: [STDOUT1, STDOUT2],
      status: "running",
      stale_inputs: null,
      timestamp: new Date(20).getTime() as Seconds,
    });

    const cell = cells[0];
    expect(cell.consoleOutputs).toMatchInlineSnapshot(`
      [
        {
          "channel": "stdout",
          "data": "output1output2",
          "mimetype": "text/plain",
          "timestamp": 1,
        },
      ]
    `);
  });

  it("can clear output of a single cell", () => {
    // Set up initial state with output
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: {
        channel: "output",
        mimetype: "text/plain",
        data: "test output",
        timestamp: 0,
      },
      console: {
        channel: "stdout",
        mimetype: "text/plain",
        data: "console output",
        timestamp: 0,
      },
      status: "idle",
      stale_inputs: null,
      timestamp: new Date(33).getTime() as Seconds,
    });

    // Verify initial state has output
    let cell = cells[0];
    expect(cell.output).not.toBeNull();
    expect(cell.consoleOutputs.length).toBe(1);

    // Clear output
    actions.clearCellOutput({ cellId: firstCellId });

    // Verify output is cleared
    cell = cells[0];
    expect(cell.output).toBeNull();
    expect(cell.consoleOutputs).toEqual([]);
  });

  it("can clear console output of a single cell", () => {
    // Set up initial state with output
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: {
        channel: "output",
        mimetype: "text/plain",
        data: "test output",
        timestamp: 0,
      },
      console: {
        channel: "stdout",
        mimetype: "text/plain",
        data: "console output",
        timestamp: 0,
      },
      status: "idle",
      stale_inputs: null,
      timestamp: new Date(33).getTime() as Seconds,
    });

    // Add a stdin console output that should be preserved
    actions.handleCellMessage({
      cell_id: firstCellId,
      console: {
        channel: "stdin",
        mimetype: "text/plain",
        data: "stdin prompt",
        timestamp: 0,
      },
      status: "idle",
      stale_inputs: null,
      timestamp: new Date(34).getTime() as Seconds,
    });

    // Verify initial state has output and console outputs
    let cell = cells[0];
    expect(cell.output).not.toBeNull();
    expect(cell.consoleOutputs.length).toBe(2);

    // Clear console output
    actions.clearCellConsoleOutput({ cellId: firstCellId });

    // Verify only console output is cleared, but stdin is preserved
    cell = cells[0];
    expect(cell.output).not.toBeNull(); // Output should remain
    expect(cell.consoleOutputs.length).toBe(1);
    expect(cell.consoleOutputs[0].channel).toBe("stdin");
    expect(cell.consoleOutputs[0].data).toBe("stdin prompt");
  });

  it("can clear output of all cells", () => {
    // Create multiple cells with output
    seedCell({ cellId: firstCellId, before: false });
    const secondCellId = state.cellIds.atOrThrow(FIRST_COLUMN).atOrThrow(1);

    // Add output to both cells
    const outputMessage = {
      output: {
        channel: "output",
        mimetype: "text/plain",
        data: "test output",
        timestamp: 0,
      },
      console: {
        channel: "stdout",
        mimetype: "text/plain",
        data: "console output",
        timestamp: 0,
      },
      status: "idle",
      stale_inputs: null,
      timestamp: new Date(33).getTime() as Seconds,
    } as const;

    actions.handleCellMessage({
      ...outputMessage,
      cell_id: firstCellId,
    });
    actions.handleCellMessage({
      ...outputMessage,
      cell_id: secondCellId,
    });

    // Verify initial state has output
    expect(state.cellRuntime[firstCellId].output).not.toBeNull();
    expect(state.cellRuntime[firstCellId].consoleOutputs.length).toBe(1);
    expect(state.cellRuntime[secondCellId].output).not.toBeNull();
    expect(state.cellRuntime[secondCellId].consoleOutputs.length).toBe(1);

    // Clear all outputs
    actions.clearAllCellOutputs();

    // Verify all outputs are cleared
    expect(state.cellRuntime[firstCellId].output).toBeNull();
    expect(state.cellRuntime[firstCellId].consoleOutputs).toEqual([]);
    expect(state.cellRuntime[secondCellId].output).toBeNull();
    expect(state.cellRuntime[secondCellId].consoleOutputs).toEqual([]);
  });

  it("can clear all outputs", () => {
    // Add a cell and give it output
    seedCell({
      cellId: firstCellId,
      before: false,
    });

    const cell1Id = cells[0].id;
    const cell2Id = cells[1].id;

    // Manually set output for the cells
    state.cellRuntime[cell1Id].output = {
      channel: "output",
      mimetype: "text/plain",
      data: "output1",
      timestamp: 0 as Seconds,
    };
    state.cellRuntime[cell2Id].output = {
      channel: "output",
      mimetype: "text/plain",
      data: "output2",
      timestamp: 0 as Seconds,
    };

    actions.clearAllCellOutputs();

    expect(state.cellRuntime[cell1Id].output).toBeNull();
    expect(state.cellRuntime[cell2Id].output).toBeNull();
  });

  describe("releaseCellAtoms", () => {
    it("atom families cache atoms until explicitly removed", () => {
      const { cellDataAtom, cellRuntimeAtom, cellHandleAtom } =
        exportedForTesting;

      seedCell({ cellId: firstCellId, before: false });
      const newCellId = state.cellIds.inOrderIds[1];

      const dataAtom1 = cellDataAtom(newCellId);
      const runtimeAtom1 = cellRuntimeAtom(newCellId);
      const handleAtom1 = cellHandleAtom(newCellId);

      // accesses return cached atoms (same reference)
      const dataAtom2 = cellDataAtom(newCellId);
      const runtimeAtom2 = cellRuntimeAtom(newCellId);
      const handleAtom2 = cellHandleAtom(newCellId);

      expect(dataAtom2).toBe(dataAtom1);
      expect(runtimeAtom2).toBe(runtimeAtom1);
      expect(handleAtom2).toBe(handleAtom1);
    });
  });
});

describe("createTracebackInfoAtom", () => {
  const store = createStore();

  it("returns undefined when cell has no errors", async () => {
    store.set(
      notebookAtom,
      MockNotebook.notebookState({
        cellData: {
          [cellId("cell1")]: {
            id: cellId("cell1"),
            name: "cell1",
            code: "",
          },
        },
      }),
    );

    const tracebackAtom = exportedForTesting.createTracebackInfoAtom(
      cellId("cell1"),
    );
    const traceback = store.get(tracebackAtom);

    expect(traceback).toBeUndefined();
  });

  it("extracts lineno from syntax errors", async () => {
    store.set(
      notebookAtom,
      MockNotebook.notebookState({
        cellData: {
          [cellId("cell1")]: {
            id: cellId("cell1"),
            name: "cell1",
            code: "x = 1",
          },
        },
        cellRuntime: {
          [cellId("cell1")]: {
            output: {
              channel: "marimo-error",
              data: [{ type: "syntax", msg: "Syntax error", lineno: 5 }],
              mimetype: "application/vnd.marimo+error",
            },
          },
        },
      }),
    );

    const tracebackAtom = exportedForTesting.createTracebackInfoAtom(
      cellId("cell1"),
    );
    const traceback = store.get(tracebackAtom);

    expect(traceback).toBeDefined();
    expect(traceback).toHaveLength(1);
    expect(traceback![0]).toEqual({
      kind: "cell",
      cellId: cellId("cell1"),
      lineNumber: 5,
    });
  });

  it("handles syntax errors with lineno = 0", async () => {
    store.set(
      notebookAtom,
      MockNotebook.notebookState({
        cellData: {
          [cellId("cell1")]: {
            id: cellId("cell1"),
            name: "cell1",
            code: "x = 1",
          },
        },
        cellRuntime: {
          [cellId("cell1")]: {
            output: {
              channel: "marimo-error",
              data: [{ type: "syntax", msg: "Syntax error", lineno: 0 }],
              mimetype: "application/vnd.marimo+error",
            },
          },
        },
      }),
    );

    const tracebackAtom = exportedForTesting.createTracebackInfoAtom(
      cellId("cell1"),
    );
    const traceback = store.get(tracebackAtom);
    expect(traceback).toBeDefined();
    expect(traceback).toHaveLength(1);
    expect(traceback![0].lineNumber).toBe(0);
  });

  it("ignores syntax errors with lineno = null", () => {
    store.set(
      notebookAtom,
      MockNotebook.notebookState({
        cellData: {
          [cellId("cell1")]: {
            id: cellId("cell1"),
            name: "cell1",
            code: "x = 1",
          },
        },
        cellRuntime: {
          [cellId("cell1")]: {
            output: {
              channel: "marimo-error",
              data: [{ type: "syntax", msg: "Syntax error", lineno: null }],
              mimetype: "application/vnd.marimo+error",
            },
          },
        },
      }),
    );

    const tracebackAtom = exportedForTesting.createTracebackInfoAtom(
      cellId("cell1"),
    );
    const traceback = store.get(tracebackAtom);

    expect(traceback).toBeUndefined();
  });

  it("handles multiple syntax errors", () => {
    store.set(
      notebookAtom,
      MockNotebook.notebookState({
        cellData: {
          [cellId("cell1")]: {
            id: cellId("cell1"),
            name: "cell1",
            code: "x = 1",
          },
        },
        cellRuntime: {
          [cellId("cell1")]: {
            output: {
              channel: "marimo-error",
              data: [
                { type: "syntax", msg: "Syntax error", lineno: 3 },
                { type: "syntax", msg: "Syntax error", lineno: 7 },
              ],
              mimetype: "application/vnd.marimo+error",
            },
          },
        },
      }),
    );

    const tracebackAtom = exportedForTesting.createTracebackInfoAtom(
      cellId("cell1"),
    );
    const traceback = store.get(tracebackAtom);
    expect(traceback).toBeDefined();
    expect(traceback).toHaveLength(2);
    expect(traceback![0].lineNumber).toBe(3);
    expect(traceback![1].lineNumber).toBe(7);
  });

  it("returns undefined when cell is queued", async () => {
    store.set(
      notebookAtom,
      MockNotebook.notebookState({
        cellData: {
          [cellId("cell1")]: {
            id: cellId("cell1"),
            name: "cell1",
            code: "x = 1",
          },
        },
        cellRuntime: {
          [cellId("cell1")]: {
            output: {
              channel: "marimo-error",
              data: [{ type: "syntax", msg: "Syntax error", lineno: 1 }],
              mimetype: "application/vnd.marimo+error",
            },
            status: "queued",
          },
        },
      }),
    );

    const tracebackAtom = exportedForTesting.createTracebackInfoAtom(
      cellId("cell1"),
    );
    const traceback = store.get(tracebackAtom);

    expect(traceback).toBeUndefined();
  });

  it("returns undefined when cell is running", () => {
    store.set(
      notebookAtom,
      MockNotebook.notebookState({
        cellData: {
          [cellId("cell1")]: {
            id: cellId("cell1"),
            name: "cell1",
            code: "x = 1",
          },
        },
        cellRuntime: {
          [cellId("cell1")]: {
            output: {
              channel: "marimo-error",
              data: [{ type: "syntax", msg: "Syntax error", lineno: 1 }],
              mimetype: "application/vnd.marimo+error",
            },
            status: "running",
          },
        },
      }),
    );

    const tracebackAtom = exportedForTesting.createTracebackInfoAtom(
      cellId("cell1"),
    );
    const traceback = store.get(tracebackAtom);

    expect(traceback).toBeUndefined();
  });
});

describe("kernel-ready", () => {
  const CELL_A = cellId("A");
  const CELL_B = cellId("B");

  const hydratedState = () =>
    MockNotebook.notebookState({
      cellData: {
        [CELL_A]: { id: CELL_A, code: "1" },
        [CELL_B]: { id: CELL_B, code: "2" },
      },
      cellRuntime: {
        [CELL_A]: {
          output: {
            channel: "output",
            mimetype: "text/plain",
            data: "hydrated-A",
            timestamp: 0,
          },
        },
        [CELL_B]: {
          consoleOutputs: [
            {
              channel: "stdout",
              mimetype: "text/plain",
              data: "hydrated-B-stdout",
              timestamp: 0,
            },
          ],
        },
      },
    });

  it("setLastRun records what the kernel last ran", () => {
    const state = hydratedState();
    const next = exportedForTesting.reducer(state, {
      type: "setLastRun",
      payload: {
        lastCodeRun: { [CELL_A]: "0" },
        lastExecutionTime: { [CELL_A]: 5 },
      },
    });

    expect(next.cellData[CELL_A]).toMatchObject({
      lastCodeRun: "0",
      lastExecutionTime: 5,
      edited: true,
    });
    expect(next.cellData[CELL_B]).toMatchObject({
      lastCodeRun: null,
      lastExecutionTime: null,
      edited: false,
    });
    expect(next.cellRuntime).toBe(state.cellRuntime);
  });

  it("resetCellRuntimes starts every cell's runtime over", () => {
    const next = exportedForTesting.reducer(hydratedState(), {
      type: "resetCellRuntimes",
      payload: undefined,
    });

    expect(next.cellRuntime[CELL_A].output).toBeNull();
    expect(next.cellRuntime[CELL_B].consoleOutputs).toEqual([]);
  });

  describe("resetCellRuntimes in WASM", () => {
    beforeEach(async () => {
      const { isWasm } = await import("@/core/wasm/utils");
      vi.mocked(isWasm).mockReturnValue(true);
    });

    afterEach(async () => {
      const { isWasm } = await import("@/core/wasm/utils");
      vi.mocked(isWasm).mockReturnValue(false);
    });

    it("keeps hydrated outputs and console", () => {
      const next = exportedForTesting.reducer(hydratedState(), {
        type: "resetCellRuntimes",
        payload: undefined,
      });

      expect(next.cellRuntime[CELL_A].output).toMatchObject({
        data: "hydrated-A",
      });
      expect(next.cellRuntime[CELL_B].consoleOutputs[0]).toMatchObject({
        data: "hydrated-B-stdout",
      });
    });

    it("starts cells with no prior runtime over", () => {
      const state = MockNotebook.notebookState({
        cellData: { [CELL_A]: { id: CELL_A, code: "1" } },
      });
      const next = exportedForTesting.reducer(state, {
        type: "resetCellRuntimes",
        payload: undefined,
      });

      expect(next.cellRuntime[CELL_A].output).toBeNull();
      expect(next.cellRuntime[CELL_A].consoleOutputs).toEqual([]);
    });
  });
});
