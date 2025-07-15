/* Copyright 2024 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import {
  afterAll,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import type { CellHandle } from "@/components/editor/Cell";
import { CellId } from "@/core/cells/ids";
import { foldAllBulk, unfoldAllBulk } from "@/core/codemirror/editing/commands";
import { adaptiveLanguageConfiguration } from "@/core/codemirror/language/extension";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import type { OutputMessage } from "@/core/kernel/messages";
import { type CollapsibleTree, MultiColumn } from "@/utils/id-tree";
import type { Seconds } from "@/utils/time";
import {
  exportedForTesting,
  flattenTopLevelNotebookCells,
  type NotebookState,
  SETUP_CELL_ID,
} from "../cells";
import {
  focusAndScrollCellIntoView,
  scrollToBottom,
  scrollToTop,
} from "../scrollCellIntoView";
import type { CellData } from "../types";

vi.mock("@/core/codemirror/editing/commands", () => ({
  foldAllBulk: vi.fn(),
  unfoldAllBulk: vi.fn(),
}));
vi.mock("../scrollCellIntoView", async (importOriginal) => {
  const actual = await importOriginal();
  return {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ...(actual as any),
    scrollToTop: vi.fn(),
    scrollToBottom: vi.fn(),
    focusAndScrollCellIntoView: vi.fn(),
  };
});

const FIRST_COLUMN = 0;
const SECOND_COLUMN = 1;

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
        cellId: "cell1" as CellId,
        completionConfig: {
          activate_on_typing: true,
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

  const actions = createActions((action) => {
    state = reducer(state, action);
    for (const [cellId, handle] of Object.entries(state.cellHandles)) {
      if (!handle.current) {
        const view = createEditor(state.cellData[cellId as CellId].code);
        const handle: CellHandle = {
          editorView: view,
          editorViewOrNull: view,
        };
        state.cellHandles[cellId as CellId] = { current: handle };
      }
    }
    cells = flattenTopLevelNotebookCells(state);
  });

  let i = 0;
  const originalCreate = CellId.create.bind(CellId);

  beforeAll(() => {
    CellId.create = () => {
      return `${i++}` as CellId;
    };
  });

  beforeEach(() => {
    i = 0;

    state = initialNotebookState();
    state.cellIds = MultiColumn.from([]);
    actions.createNewCell({ cellId: "__end__", before: false });
    firstCellId = state.cellIds.inOrderIds[0];
  });

  afterAll(() => {
    CellId.create = originalCreate;
  });

  it("can add a cell after another cell", () => {
    actions.createNewCell({
      cellId: firstCellId,
      before: false,
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [0] ''

      [1] ''
      "
    `);
  });

  it("can add a cell to the end with code", () => {
    actions.createNewCell({
      cellId: "__end__",
      code: "import numpy as np",
      before: false,
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [0] ''

      [1] 'import numpy as np'
      "
    `);

    // Cell should be added to the end and edited
    expect(cells[1].code).toBe("import numpy as np");
    expect(cells[1].edited).toBe(true);
    expect(cells[1].lastCodeRun).toBe(null);
  });

  it("can add a cell before another cell", () => {
    actions.createNewCell({
      cellId: firstCellId,
      before: true,
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [1] ''

      [0] ''
      "
    `);
  });

  it("can delete a Python cell and undo delete", () => {
    actions.createNewCell({
      cellId: firstCellId,
      before: false,
    });
    actions.deleteCell({
      cellId: firstCellId,
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [1] ''
      "
    `);

    // undo
    actions.undoDeleteCell();
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [2] ''

      [1] ''
      "
    `);
  });

  it("can delete a SQL cell and undo delete", () => {
    actions.createNewCell({
      cellId: firstCellId,
      before: false,
      code: `df = mo.sql("""SELECT * FROM table""")`,
    });
    const newCellId = state.cellIds.getColumns()[0].atOrThrow(1);
    actions.deleteCell({
      cellId: newCellId,
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [0] ''
      "
    `);

    // undo
    actions.undoDeleteCell();
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [0] ''

      [2] 'df = mo.sql("""SELECT * FROM table""")'
      "
    `);
  });

  it("can delete a Markdown cell and undo delete", () => {
    const text = "The quick brown fox jumps over the lazy dog.";
    actions.createNewCell({
      cellId: firstCellId,
      before: false,
      code: `mo.md(r"""${text}""")`,
    });
    const newCellId = state.cellIds.getColumns()[0].atOrThrow(1);
    actions.deleteCell({
      cellId: newCellId,
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [0] ''
      "
    `);

    // undo
    actions.undoDeleteCell();
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [0] ''

      [2] 'mo.md(r"""The quick brown fox jumps over the lazy dog.""")'
      "
    `);
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

  it("can move a cell", () => {
    actions.createNewCell({
      cellId: firstCellId,
      before: false,
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [0] ''

      [1] ''
      "
    `);

    // move first cell to the end
    actions.moveCell({
      cellId: firstCellId,
      before: false,
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [1] ''

      [0] ''
      "
    `);

    // move it back
    actions.moveCell({
      cellId: firstCellId,
      before: true,
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [0] ''

      [1] ''
      "
    `);

    // Add a column breakpoint to test left/right movement
    actions.addColumnBreakpoint({ cellId: "1" as CellId });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      > col 0
      [0] ''

      > col 1
      [1] ''
      "
    `);

    // Move cell right
    actions.moveCell({
      cellId: firstCellId,
      direction: "right",
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      > col 0


      > col 1
      [0] ''

      [1] ''
      "
    `);

    // Move cell left
    actions.moveCell({
      cellId: firstCellId,
      direction: "left",
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      > col 0
      [0] ''

      > col 1
      [1] ''
      "
    `);

    // Try to move cell left when it's already in leftmost column (should noop)
    actions.moveCell({
      cellId: firstCellId,
      direction: "left",
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      > col 0
      [0] ''

      > col 1
      [1] ''
      "
    `);

    // Try to move cell right when it's already in rightmost column (should noop)
    actions.moveCell({
      cellId: "1" as CellId,
      direction: "right",
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      > col 0
      [0] ''

      > col 1
      [1] ''
      "
    `);
  });

  it("can drag and drop a cell", () => {
    actions.createNewCell({
      cellId: firstCellId,
      before: false,
    });
    actions.createNewCell({
      cellId: "1" as CellId,
      before: false,
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [0] ''

      [1] ''

      [2] ''
      "
    `);

    // drag first cell to the end
    actions.dropCellOverCell({
      cellId: firstCellId,
      overCellId: "2" as CellId,
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [1] ''

      [2] ''

      [0] ''
      "
    `);

    // drag it back to the middle
    actions.dropCellOverCell({
      cellId: firstCellId,
      overCellId: "2" as CellId,
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [1] ''

      [0] ''

      [2] ''
      "
    `);
  });

  it("can run cell and receive cell messages", () => {
    // HAPPY PATH
    /////////////////
    // Initial state
    let cell = cells[0];
    expect(cell.status).toBe("idle");
    expect(cell.lastCodeRun).toBe(null);
    expect(cell.edited).toBe(false);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Prepare for run
    actions.prepareForRun({
      cellId: firstCellId,
    });
    cell = cells[0];
    expect(cell.status).toBe("queued");
    expect(cell.lastCodeRun).toBe("import marimo as mo");
    expect(cell.edited).toBe(false);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Update code should be unedited
    actions.updateCellCode({
      cellId: firstCellId,
      code: "import marimo as mo",
      formattingChange: false,
    });
    cell = cells[0];
    expect(cell.edited).toBe(false);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all
  });

  it("errors reset status to idle", () => {
    // Initial state
    let cell = cells[0];
    expect(cell.status).toBe("idle");
    expect(cell.lastCodeRun).toBe(null);
    expect(cell.edited).toBe(false);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Prepare for run
    actions.prepareForRun({
      cellId: firstCellId,
    });
    cell = cells[0];
    expect(cell.status).toBe("queued");
    expect(cell.lastCodeRun).toBe("import marimo as mo");
    expect(cell.edited).toBe(false);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all
  });

  it("can run a stale cell", () => {
    // Update code of first cell
    actions.updateCellCode({
      cellId: firstCellId,
      code: "import marimo as mo",
      formattingChange: false,
    });
    // Add cell
    actions.createNewCell({
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
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all
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

  it("can update a cells config", () => {
    const firstCellId = cells[0].id;
    let cell = cells[0];
    // Starts empty
    expect(cell.config).toEqual({
      disabled: false,
      hide_code: false,
      column: null,
    });

    actions.updateCellConfig({
      cellId: firstCellId,
      config: { disabled: true },
    });
    cell = cells[0];
    expect(cell.config.disabled).toBe(true);

    // Revert
    actions.updateCellConfig({
      cellId: firstCellId,
      config: { disabled: false },
    });
    cell = cells[0];
    expect(cell.config.disabled).toBe(false);
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
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Receive stop output
    actions.handleCellMessage({
      cell_id: firstCellId,
      output: {
        channel: "marimo-error",
        mimetype: "application/vnd.marimo+error",
        data: [
          {
            msg: "This cell wasn't run because an ancestor was stopped with `mo.stop`: ",
            raising_cell: "2" as CellId,
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
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect((cell.output?.data as any)[0].msg).toBe(
      "This cell wasn't run because an ancestor was stopped with `mo.stop`: ",
    );
    expect(cell.stopped).toBe(true);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all
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
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Prepare for run
    actions.prepareForRun({
      cellId: firstCellId,
    });
    cell = cells[0];
    expect(cell.status).toBe("queued");
    expect(cell.consoleOutputs).toEqual([]);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    cell = cells[0];
    expect(cell.consoleOutputs).toEqual([STDOUT]);
    expect(cell.status).toBe("running");
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell.consoleOutputs).toEqual([STDOUT, STD_IN_1]);
    expect(cell.status).toBe("running");
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Response to stdin
    actions.setStdinResponse({
      response: "Marimo!",
      cellId: firstCellId,
      outputIndex: 1,
    });
    cell = cells[0];
    expect(cell.consoleOutputs).toEqual([
      STDOUT,
      {
        ...STD_IN_1,
        response: "Marimo!",
      },
    ]);
    expect(cell.status).toBe("running");
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell.consoleOutputs).toEqual([
      STDOUT,
      { ...STD_IN_1, response: "Marimo!" },
      STD_IN_2,
    ]);
    expect(cell.status).toBe("running");
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell.consoleOutputs).toEqual([
      STDOUT,
      { ...STD_IN_1, response: "Marimo!" },
      { ...STD_IN_2, response: "" },
    ]);
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
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell.consoleOutputs).toEqual([OLD_STDOUT]); // Old stays there until it starts running
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell.consoleOutputs).toEqual([OLD_STDOUT]); // Old stays there until it starts running
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell.consoleOutputs).toEqual([]);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell.consoleOutputs).toEqual([STDOUT]);
    expect(cell.status).toBe("idle");
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all
  });

  it("can send a cell to the top", () => {
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({ cellId: "1" as CellId, before: false });
    actions.sendToTop({ cellId: "2" as CellId });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [2] ''

      [0] ''

      [1] ''
      "
    `);
  });

  it("can send a cell to the bottom", () => {
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({ cellId: "1" as CellId, before: false });
    actions.sendToBottom({ cellId: firstCellId });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [1] ''

      [2] ''

      [0] ''
      "
    `);
  });

  it("can focus cells", () => {
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({ cellId: "1" as CellId, before: false });

    actions.focusCell({ cellId: "1" as CellId, before: true });
    expect(focusAndScrollCellIntoView).toHaveBeenCalledWith(
      expect.objectContaining({
        cellId: "0" as CellId,
      }),
    );

    actions.focusTopCell();
    expect(scrollToTop).toHaveBeenCalled();

    actions.focusBottomCell();
    expect(scrollToBottom).toHaveBeenCalled();
  });

  it("can update cell name", () => {
    actions.updateCellName({ cellId: firstCellId, name: "Test Cell" });
    expect(state.cellData[firstCellId].name).toBe("Test Cell");
  });

  it("can set cell IDs and codes", () => {
    const newIds = ["3", "4", "5"] as CellId[];
    const newCodes = ["code1", "code2", "code3"];

    actions.setCellIds({ cellIds: newIds });
    expect(state.cellIds.atOrThrow(FIRST_COLUMN).topLevelIds).toEqual(newIds);

    // When codeIsStale is false, lastCodeRun should match code
    actions.setCellCodes({
      codes: newCodes,
      ids: newIds,
      codeIsStale: false,
    });
    newIds.forEach((id, index) => {
      expect(state.cellData[id].code).toBe(newCodes[index]);
      expect(state.cellData[id].lastCodeRun).toBe(newCodes[index]);
      expect(state.cellData[id].edited).toBe(false);
    });

    // When codeIsStale is true, lastCodeRun should not change
    const staleCodes = ["stale1", "stale2", "stale3"];
    actions.setCellCodes({
      codes: staleCodes,
      ids: newIds,
      codeIsStale: true,
    });
    newIds.forEach((id, index) => {
      expect(state.cellData[id].code).toBe(staleCodes[index]);
      expect(state.cellData[id].lastCodeRun).toBe(newCodes[index]);
      expect(state.cellData[id].edited).toBe(true);
    });
  });

  it("can can add a new cell with/without stale code", () => {
    actions.setCellCodes({
      codes: ["new code"],
      ids: ["2"] as CellId[],
      codeIsStale: false,
    });

    expect(state.cellData["2" as CellId].code).toBe("new code");
    expect(state.cellData["2" as CellId].edited).toBe(false);
    expect(state.cellData["2" as CellId].lastCodeRun).toBe("new code");

    actions.setCellCodes({
      codes: ["new code 2"],
      ids: ["9"] as CellId[],
      codeIsStale: true,
    });

    expect(state.cellData["9" as CellId].code).toBe("new code 2");
    expect(state.cellData["9" as CellId].edited).toBe(true);
    expect(state.cellData["9" as CellId].lastCodeRun).toBe(null);
  });

  it("can partial update cell codes", () => {
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({ cellId: "1" as CellId, before: false });

    expect(state.cellIds.inOrderIds).toEqual(["0", "1", "2"]);
    expect(state.cellData["0" as CellId].code).toBe("");
    expect(state.cellData["1" as CellId].code).toBe("");
    expect(state.cellData["2" as CellId].code).toBe("");

    // Update cell 1
    actions.setCellCodes({
      codes: ["new code 2"],
      ids: ["1"] as CellId[],
      codeIsStale: false,
    });

    expect(state.cellIds.inOrderIds).toEqual(["0", "1", "2"]);
    expect(state.cellData["0" as CellId].code).toBe("");
    expect(state.cellData["1" as CellId].code).toBe("new code 2");
    expect(state.cellData["1" as CellId].edited).toBe(false);
    expect(state.cellData["2" as CellId].code).toBe("");
  });

  it("can set cell codes with new cell ids, while preserving the old cell data", () => {
    actions.setCellCodes({
      codes: ["code1", "code2", "code3"],
      ids: ["3", "4", "5"] as CellId[],
      codeIsStale: false,
    });
    expect(state.cellData["3" as CellId].code).toBe("code1");
    expect(state.cellData["4" as CellId].code).toBe("code2");
    expect(state.cellData["5" as CellId].code).toBe("code3");

    // Update with some new cell ids and some old cell ids
    actions.setCellIds({ cellIds: ["1", "2", "3", "4"] as CellId[] });
    actions.setCellCodes({
      codes: ["new1", "new2", "code1", "code2"],
      ids: ["1", "2", "3", "4"] as CellId[],
      codeIsStale: false,
    });
    expect(state.cellData["1" as CellId].code).toBe("new1");
    expect(state.cellData["2" as CellId].code).toBe("new2");
    expect(state.cellData["3" as CellId].code).toBe("code1");
    expect(state.cellData["4" as CellId].code).toBe("code2");
    expect(state.cellIds.inOrderIds).toEqual(["1", "2", "3", "4"]);
    // Cell 5 data is preserved (possibly used for tracing), but it's not in the cellIds
    expect(state.cellData["5" as CellId]).not.toBeUndefined();
  });

  it("can fold and unfold all cells", () => {
    actions.foldAll();
    expect(foldAllBulk).toHaveBeenCalled();

    actions.unfoldAll();
    expect(unfoldAllBulk).toHaveBeenCalled();
  });

  it("can clear logs", () => {
    state.cellLogs = [
      { level: "stderr", message: "log1", timestamp: 0, cellId: firstCellId },
      { level: "stderr", message: "log1", timestamp: 0, cellId: firstCellId },
    ];
    actions.clearLogs();
    expect(state.cellLogs).toEqual([]);
  });

  it("can collapse and expand cells", () => {
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({
      cellId: "1" as CellId,
      before: false,
      code: "# Header",
    });
    actions.createNewCell({
      cellId: "2" as CellId,
      before: false,
      code: "## Subheader",
    });

    const id = state.cellIds.atOrThrow(FIRST_COLUMN).atOrThrow(1);
    state.cellRuntime[id] = {
      ...state.cellRuntime[id],
      outline: {
        items: [{ name: "Header", level: 1, by: { id: "header" } }],
      },
    };

    actions.collapseCell({ cellId: id });
    expect(state.cellIds.atOrThrow(FIRST_COLUMN).isCollapsed(id)).toBe(true);

    actions.expandCell({ cellId: id });
    expect(state.cellIds.atOrThrow(FIRST_COLUMN).isCollapsed(id)).toBe(false);
  });

  it("can collapse and expand all cells in multiple columns", () => {
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({
      cellId: "1" as CellId,
      before: false,
      code: "# First Column Header",
    });
    actions.createNewCell({
      cellId: "2" as CellId,
      before: false,
      code: "## First Column Subheader",
    });

    actions.addColumnBreakpoint({ cellId: "2" as CellId });

    actions.createNewCell({
      cellId: "3" as CellId,
      before: false,
      code: "# Second Column Header",
    });
    actions.createNewCell({
      cellId: "4" as CellId,
      before: false,
      code: "## Second Column Subheader",
    });

    const firstColumnHeaderId = state.cellIds
      .atOrThrow(FIRST_COLUMN)
      .atOrThrow(1);
    state.cellRuntime[firstColumnHeaderId] = {
      ...state.cellRuntime[firstColumnHeaderId],
      outline: {
        items: [
          { name: "First Column Header", level: 1, by: { id: "header" } },
        ],
      },
    };

    const secondColumnHeaderId = state.cellIds
      .atOrThrow(SECOND_COLUMN)
      .atOrThrow(0);
    state.cellRuntime[secondColumnHeaderId] = {
      ...state.cellRuntime[secondColumnHeaderId],
      outline: {
        items: [
          { name: "Second Column Header", level: 1, by: { id: "header" } },
        ],
      },
    };

    actions.collapseAllCells();
    expect(
      state.cellIds.atOrThrow(FIRST_COLUMN).isCollapsed(firstColumnHeaderId),
    ).toBe(true);
    expect(
      state.cellIds.atOrThrow(SECOND_COLUMN).isCollapsed(secondColumnHeaderId),
    ).toBe(true);

    actions.expandAllCells();
    expect(
      state.cellIds.atOrThrow(FIRST_COLUMN).isCollapsed(firstColumnHeaderId),
    ).toBe(false);
    expect(
      state.cellIds.atOrThrow(SECOND_COLUMN).isCollapsed(secondColumnHeaderId),
    ).toBe(false);
  });

  it("can collapse and expand nested cells in one call", () => {
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({
      cellId: "1" as CellId,
      before: false,
      code: "# Header",
    });
    actions.createNewCell({
      cellId: "2" as CellId,
      before: false,
      code: "## Subheader",
    });
    actions.createNewCell({
      cellId: "3" as CellId,
      before: false,
      code: "### Subsubheader",
    });

    const headerId = state.cellIds.atOrThrow(FIRST_COLUMN).atOrThrow(1);
    state.cellRuntime[headerId] = {
      ...state.cellRuntime[headerId],
      outline: {
        items: [{ name: "Header", level: 1, by: { id: "header" } }],
      },
    };

    const subheaderId = state.cellIds.atOrThrow(FIRST_COLUMN).atOrThrow(2);
    state.cellRuntime[subheaderId] = {
      ...state.cellRuntime[subheaderId],
      outline: {
        items: [{ name: "Subheader", level: 2, by: { id: "subheader" } }],
      },
    };

    // Check if both the parent and child are collapsed
    actions.collapseAllCells();
    expect(state.cellIds.atOrThrow(FIRST_COLUMN).isCollapsed(headerId)).toBe(
      true,
    );
    actions.expandCell({ cellId: headerId });
    expect(state.cellIds.atOrThrow(FIRST_COLUMN).isCollapsed(subheaderId)).toBe(
      true,
    );
    actions.collapseCell({ cellId: headerId });

    // Check if both the parent and child are expanded
    actions.expandAllCells();
    expect(state.cellIds.atOrThrow(FIRST_COLUMN).isCollapsed(headerId)).toBe(
      false,
    );
    expect(state.cellIds.atOrThrow(FIRST_COLUMN).isCollapsed(subheaderId)).toBe(
      false,
    );
  });

  it("can show hidden cells", () => {
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({ cellId: "1" as CellId, before: false });
    actions.collapseCell({ cellId: firstCellId });

    actions.showCellIfHidden({ cellId: "1" as CellId });
    expect(state.cellIds.atOrThrow(FIRST_COLUMN).isCollapsed(firstCellId)).toBe(
      false,
    );
  });

  it("can split and undo split cells", () => {
    actions.createNewCell({
      cellId: firstCellId,
      before: false,
      code: "line1\nline2",
    });
    const nextCellId = state.cellIds.atOrThrow(FIRST_COLUMN).atOrThrow(1);

    const originalCellCount = state.cellIds.atOrThrow(FIRST_COLUMN).length;
    // Move cursor to the second line
    const editor = state.cellHandles[nextCellId].current?.editorView;
    if (!editor) {
      throw new Error("Editor not found");
    }
    editor.dispatch({ selection: { anchor: 5, head: 5 } });
    actions.splitCell({ cellId: nextCellId });
    expect(state.cellIds.atOrThrow(FIRST_COLUMN).length).toBe(
      originalCellCount + 1,
    );
    expect(state.cellData[nextCellId].code).toBe("line1");
    expect(
      state.cellData[state.cellIds.atOrThrow(FIRST_COLUMN).atOrThrow(2)].code,
    ).toBe("line2");

    actions.undoSplitCell({ cellId: nextCellId, snapshot: "line1\nline2" });
    expect(state.cellIds.atOrThrow(FIRST_COLUMN).length).toBe(
      originalCellCount,
    );
    expect(state.cellData[nextCellId].code).toBe("line1\nline2");
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
    expect(cell.consoleOutputs).toEqual([STDOUT1, STDOUT2]);
  });

  it("can add a column breakpoint", () => {
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({ cellId: "1" as CellId, before: false });
    actions.createNewCell({ cellId: "2" as CellId, before: false });

    expect(state.cellIds.getColumns().length).toBe(1);
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [0] ''

      [1] ''

      [2] ''

      [3] ''
      "
    `);

    actions.addColumnBreakpoint({ cellId: "2" as CellId });

    expect(state.cellIds.getColumns().length).toBe(2);
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      > col 0
      [0] ''

      [1] ''

      > col 1
      [2] ''

      [3] ''
      "
    `);

    // Check that the cells are in the correct columns
    expect(state.cellIds.getColumns()[0].topLevelIds).toEqual(["0", "1"]);
    expect(state.cellIds.getColumns()[1].topLevelIds).toEqual(["2", "3"]);
  });

  it("cannot add a column breakpoint before the first cell", () => {
    expect(state.cellIds.getColumns().length).toBe(1);
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({ cellId: "1" as CellId, before: false });
    actions.addColumnBreakpoint({ cellId: firstCellId });
    expect(state.cellIds.getColumns().length).toBe(1);
  });

  it("can delete a column", () => {
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({ cellId: "1" as CellId, before: false });
    actions.createNewCell({ cellId: "2" as CellId, before: false });
    actions.addColumnBreakpoint({ cellId: "2" as CellId });

    expect(state.cellIds.getColumns().length).toBe(2);
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      > col 0
      [0] ''

      [1] ''

      > col 1
      [2] ''

      [3] ''
      "
    `);

    const columnId = state.cellIds.atOrThrow(0).id;
    actions.deleteColumn({ columnId: columnId });

    expect(state.cellIds.getColumns().length).toBe(1);
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [2] ''

      [3] ''

      [0] ''

      [1] ''
      "
    `);

    // Check that all cells are now in the remaining column
    expect(state.cellIds.getColumns()[0].topLevelIds).toEqual([
      "2",
      "3",
      "0",
      "1",
    ]);
  });

  it("deleting the last column does nothing", () => {
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({ cellId: "1" as CellId, before: false });

    const initialState = { ...state };

    actions.deleteColumn({ columnId: initialState.cellIds.atOrThrow(0).id });

    // State should not change
    expect(state).toEqual(initialState);
  });

  it("can drop a cell over another cell", () => {
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({ cellId: "1" as CellId, before: false });
    actions.createNewCell({ cellId: "2" as CellId, before: false });

    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [0] ''

      [1] ''

      [2] ''

      [3] ''
      "
    `);

    actions.dropCellOverCell({
      cellId: "0" as CellId,
      overCellId: "3" as CellId,
    });

    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [1] ''

      [2] ''

      [3] ''

      [0] ''
      "
    `);
  });

  it("can drop a cell over a new column", () => {
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({ cellId: "1" as CellId, before: false });

    expect(state.cellIds.getColumns().length).toBe(1);
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [0] ''

      [1] ''

      [2] ''
      "
    `);

    actions.dropOverNewColumn({ cellId: "1" as CellId });

    expect(state.cellIds.getColumns().length).toBe(2);
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      > col 0
      [0] ''

      [2] ''

      > col 1
      [1] ''
      "
    `);

    // Check that the cells are in the correct columns
    expect(state.cellIds.getColumns()[0].topLevelIds).toEqual(["0", "2"]);
    expect(state.cellIds.getColumns()[1].topLevelIds).toEqual(["1"]);
  });

  it("can drop a column over another column", () => {
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({ cellId: "1" as CellId, before: false });
    actions.createNewCell({ cellId: "2" as CellId, before: false });
    actions.addColumnBreakpoint({ cellId: "2" as CellId });

    expect(state.cellIds.getColumns().length).toBe(2);
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      > col 0
      [0] ''

      [1] ''

      > col 1
      [2] ''

      [3] ''
      "
    `);

    const columnId0 = state.cellIds.atOrThrow(0).id;
    const columnId1 = state.cellIds.atOrThrow(1).id;
    expect(columnId0).not.toBe(columnId1);
    actions.moveColumn({ column: columnId1, overColumn: columnId0 });

    expect(state.cellIds.getColumns().length).toBe(2);
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      > col 0
      [2] ''

      [3] ''

      > col 1
      [0] ''

      [1] ''
      "
    `);

    // Check that the columns have swapped positions
    expect(state.cellIds.getColumns()[0].topLevelIds).toEqual(["2", "3"]);
    expect(state.cellIds.getColumns()[1].topLevelIds).toEqual(["0", "1"]);
  });

  it("can compact columns", () => {
    // Create initial state with 3 columns, including an empty one
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({ cellId: "1" as CellId, before: false });
    actions.addColumnBreakpoint({ cellId: "1" as CellId });
    actions.addColumnBreakpoint({ cellId: "2" as CellId });
    actions.dropOverNewColumn({ cellId: "2" as CellId });

    expect(state.cellIds.getColumns().length).toBe(4);
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      > col 0
      [0] ''

      > col 1
      [1] ''

      > col 2


      > col 3
      [2] ''
      "
    `);

    // Check initial column structure
    expect(state.cellIds.getColumns()[0].topLevelIds).toEqual(["0"]);
    expect(state.cellIds.getColumns()[1].topLevelIds).toEqual(["1"]);
    expect(state.cellIds.getColumns()[2].topLevelIds).toEqual([]);
    expect(state.cellIds.getColumns()[3].topLevelIds).toEqual(["2"]);

    // Compact columns
    actions.compactColumns();

    expect(state.cellIds.getColumns().length).toBe(3);
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      > col 0
      [0] ''

      > col 1
      [1] ''

      > col 2
      [2] ''
      "
    `);

    // Check compacted column structure
    expect(state.cellIds.getColumns()[0].topLevelIds).toEqual(["0"]);
    expect(state.cellIds.getColumns()[1].topLevelIds).toEqual(["1"]);
    expect(state.cellIds.getColumns()[2].topLevelIds).toEqual(["2"]);
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
    actions.createNewCell({ cellId: firstCellId, before: false });
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

  it("skips creating new cell if code exists and skipIfCodeExists is true", () => {
    // Add initial cell with code
    actions.updateCellCode({
      cellId: firstCellId,
      code: "import numpy as np",
      formattingChange: false,
    });

    // Try to create new cell with same code and skipIfCodeExists
    actions.createNewCell({
      cellId: "__end__",
      code: "import numpy as np",
      before: false,
      skipIfCodeExists: true,
    });

    // Should still only have one cell
    expect(state.cellIds.inOrderIds.length).toBe(1);
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [0] 'import numpy as np'
      "
    `);

    // Verify we can still add cell with different code
    actions.createNewCell({
      cellId: "__end__",
      code: "import pandas as pd",
      before: false,
      skipIfCodeExists: true,
    });

    expect(state.cellIds.inOrderIds.length).toBe(2);
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [0] 'import numpy as np'

      [1] 'import pandas as pd'
      "
    `);
  });

  it("can create and update a setup cell", () => {
    // Create the setup cell
    actions.upsertSetupCell({ code: "# Setup code" });

    // Check that setup cell was created
    expect(state.cellData[SETUP_CELL_ID].id).toBe(SETUP_CELL_ID);
    expect(state.cellData[SETUP_CELL_ID].name).toBe("setup");
    expect(state.cellData[SETUP_CELL_ID].code).toBe("# Setup code");
    expect(state.cellData[SETUP_CELL_ID].edited).toBe(true);
    expect(state.cellIds.inOrderIds).toContain(SETUP_CELL_ID);

    // Update the setup cell
    actions.upsertSetupCell({ code: "# Updated setup code" });

    // Check that the same setup cell was updated, not duplicated
    expect(state.cellData[SETUP_CELL_ID].code).toBe("# Updated setup code");
    expect(state.cellData[SETUP_CELL_ID].edited).toBe(true);
    expect(state.cellIds.inOrderIds).toContain(SETUP_CELL_ID);
  });

  it("can delete and undelete the setup cell", () => {
    // Create the setup cell
    actions.upsertSetupCell({ code: "# Setup code" });

    // Check that setup cell was created
    expect(state.cellData[SETUP_CELL_ID].id).toBe(SETUP_CELL_ID);
    expect(state.cellData[SETUP_CELL_ID].name).toBe("setup");
    expect(state.cellData[SETUP_CELL_ID].code).toBe("# Setup code");
    expect(state.cellData[SETUP_CELL_ID].edited).toBe(true);
    expect(state.cellIds.inOrderIds).toContain(SETUP_CELL_ID);

    // Delete the setup cell
    actions.deleteCell({ cellId: SETUP_CELL_ID });

    // Check that setup cell was deleted
    expect(state.cellData[SETUP_CELL_ID]).toBeDefined(); // we keep old state
    expect(state.cellIds.inOrderIds).not.toContain(SETUP_CELL_ID);

    // Undo delete the setup cell
    actions.undoDeleteCell();

    // Check that setup cell was restored
    expect(state.cellData[SETUP_CELL_ID].id).toBe(SETUP_CELL_ID);
    expect(state.cellData[SETUP_CELL_ID].name).toBe("setup");
    expect(state.cellData[SETUP_CELL_ID].code).toBe("# Setup code");
    expect(state.cellData[SETUP_CELL_ID].edited).toBe(true);
    expect(state.cellIds.inOrderIds).toContain(SETUP_CELL_ID);
  });

  it("can clear all outputs", () => {
    // Add a cell and give it output
    actions.createNewCell({
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

  describe("moveToNextCell", () => {
    let cell1Id: CellId;
    let cell2Id: CellId;
    let cell3Id: CellId;

    beforeEach(() => {
      // Create a few cells to work with
      actions.createNewCell({ cellId: "__end__", before: false });
      actions.createNewCell({ cellId: "__end__", before: false });

      cell1Id = state.cellIds.inOrderIds[0];
      cell2Id = state.cellIds.inOrderIds[1];
      cell3Id = state.cellIds.inOrderIds[2];
    });

    it("creates new cell when moving after last cell with noCreate=false", () => {
      const initialCellCount = state.cellIds.inOrderIds.length;

      actions.moveToNextCell({
        cellId: cell3Id,
        before: false,
        noCreate: false,
      });

      expect(state.cellIds.inOrderIds.length).toBe(initialCellCount + 1);
    });

    it("creates new cell when moving before first cell with noCreate=false", () => {
      const initialCellCount = state.cellIds.inOrderIds.length;

      actions.moveToNextCell({
        cellId: cell1Id,
        before: true,
        noCreate: false,
      });

      expect(state.cellIds.inOrderIds.length).toBe(initialCellCount + 1);
    });

    it("does not create new cell when moving after last cell with noCreate=true", () => {
      const initialCellCount = state.cellIds.inOrderIds.length;
      const initialState = { ...state };

      actions.moveToNextCell({
        cellId: cell3Id,
        before: false,
        noCreate: true,
      });

      // Should not create a new cell
      expect(state.cellIds.inOrderIds.length).toBe(initialCellCount);
      // Should not crash or throw an error
      expect(state.cellIds.inOrderIds).toEqual(initialState.cellIds.inOrderIds);
    });

    it("does not create new cell when moving before first cell with noCreate=true", () => {
      const initialCellCount = state.cellIds.inOrderIds.length;
      const initialState = { ...state };

      actions.moveToNextCell({ cellId: cell1Id, before: true, noCreate: true });

      // Should not create a new cell
      expect(state.cellIds.inOrderIds.length).toBe(initialCellCount);
      // Should not crash or throw an error
      expect(state.cellIds.inOrderIds).toEqual(initialState.cellIds.inOrderIds);
    });

    it("focuses next cell when moving within bounds", () => {
      const focusSpy = vi.mocked(focusAndScrollCellIntoView);
      focusSpy.mockClear();

      actions.moveToNextCell({
        cellId: cell1Id,
        before: false,
        noCreate: true,
      });

      expect(focusSpy).toHaveBeenCalledWith({
        cellId: cell2Id,
        cell: state.cellHandles[cell2Id],
        isCodeHidden: false,
        codeFocus: "top",
        variableName: undefined,
      });
    });

    it("focuses previous cell when moving backward within bounds", () => {
      const focusSpy = vi.mocked(focusAndScrollCellIntoView);
      focusSpy.mockClear();

      actions.moveToNextCell({ cellId: cell2Id, before: true, noCreate: true });

      expect(focusSpy).toHaveBeenCalledWith({
        cellId: cell1Id,
        cell: state.cellHandles[cell1Id],
        isCodeHidden: false,
        codeFocus: "bottom",
        variableName: undefined,
      });
    });

    it("does not move focus from scratch cell", () => {
      const focusSpy = vi.mocked(focusAndScrollCellIntoView);
      focusSpy.mockClear();
      const initialState = { ...state };

      actions.moveToNextCell({
        cellId: "__scratch__" as CellId,
        before: false,
        noCreate: false,
      });

      expect(focusSpy).not.toHaveBeenCalled();
      expect(state.cellIds.inOrderIds).toEqual(initialState.cellIds.inOrderIds);
    });
  });

  describe("untouched cells functionality", () => {
    it("starts with empty untouchedNewCells set", () => {
      expect(state.untouchedNewCells).toEqual(new Set());
    });

    it("can create a new cell with hideCode option", () => {
      const initialCellCount = state.cellIds.inOrderIds.length;

      actions.createNewCell({
        cellId: "__end__",
        before: false,
        hideCode: true,
      });

      expect(state.cellIds.inOrderIds.length).toBe(initialCellCount + 1);
      const newCellId =
        state.cellIds.inOrderIds[state.cellIds.inOrderIds.length - 1];
      expect(state.untouchedNewCells.has(newCellId)).toBe(true);
    });

    it("does not add cell to untouchedNewCells when hideCode is false", () => {
      actions.createNewCell({
        cellId: "__end__",
        before: false,
        hideCode: false,
      });

      const newCellId =
        state.cellIds.inOrderIds[state.cellIds.inOrderIds.length - 1];
      expect(state.untouchedNewCells.has(newCellId)).toBe(false);
    });

    it("does not add cell to untouchedNewCells when hideCode is undefined", () => {
      actions.createNewCell({
        cellId: "__end__",
        before: false,
      });

      const newCellId =
        state.cellIds.inOrderIds[state.cellIds.inOrderIds.length - 1];
      expect(state.untouchedNewCells.has(newCellId)).toBe(false);
    });

    it("can mark a cell as touched", () => {
      // Create a cell with hideCode
      actions.createNewCell({
        cellId: "__end__",
        before: false,
        hideCode: true,
      });

      const newCellId =
        state.cellIds.inOrderIds[state.cellIds.inOrderIds.length - 1];
      expect(state.untouchedNewCells.has(newCellId)).toBe(true);

      // Mark it as touched
      actions.markTouched({ cellId: newCellId });

      expect(state.untouchedNewCells.has(newCellId)).toBe(false);
    });

    it("markTouched is idempotent", () => {
      // Create a cell with hideCode
      actions.createNewCell({
        cellId: "__end__",
        before: false,
        hideCode: true,
      });

      const newCellId =
        state.cellIds.inOrderIds[state.cellIds.inOrderIds.length - 1];
      expect(state.untouchedNewCells.has(newCellId)).toBe(true);

      // Mark it as touched multiple times
      actions.markTouched({ cellId: newCellId });
      actions.markTouched({ cellId: newCellId });
      actions.markTouched({ cellId: newCellId });

      expect(state.untouchedNewCells.has(newCellId)).toBe(false);
    });

    it("can mark a non-existent cell as touched without error", () => {
      const nonExistentCellId = "non-existent" as CellId;

      expect(() => {
        actions.markTouched({ cellId: nonExistentCellId });
      }).not.toThrow();

      expect(state.untouchedNewCells.has(nonExistentCellId)).toBe(false);
    });

    it("can handle multiple untouched cells", () => {
      // Create multiple cells with hideCode
      actions.createNewCell({
        cellId: "__end__",
        before: false,
        hideCode: true,
      });
      actions.createNewCell({
        cellId: "__end__",
        before: false,
        hideCode: true,
      });
      actions.createNewCell({
        cellId: "__end__",
        before: false,
        hideCode: false,
      });

      const cellIds = state.cellIds.inOrderIds;
      const cell1Id = cellIds[cellIds.length - 3];
      const cell2Id = cellIds[cellIds.length - 2];
      const cell3Id = cellIds[cellIds.length - 1];

      expect(state.untouchedNewCells.has(cell1Id)).toBe(true);
      expect(state.untouchedNewCells.has(cell2Id)).toBe(true);
      expect(state.untouchedNewCells.has(cell3Id)).toBe(false);

      // Mark one as touched
      actions.markTouched({ cellId: cell1Id });

      expect(state.untouchedNewCells.has(cell1Id)).toBe(false);
      expect(state.untouchedNewCells.has(cell2Id)).toBe(true);
      expect(state.untouchedNewCells.has(cell3Id)).toBe(false);
    });

    it("preserves untouched state when cells are moved", () => {
      // Create cells with hideCode
      actions.createNewCell({
        cellId: "__end__",
        before: false,
        hideCode: true,
      });
      actions.createNewCell({
        cellId: "__end__",
        before: false,
        hideCode: true,
      });

      const cellIds = state.cellIds.inOrderIds;
      const cell1Id = cellIds[cellIds.length - 2];
      const cell2Id = cellIds[cellIds.length - 1];

      expect(state.untouchedNewCells.has(cell1Id)).toBe(true);
      expect(state.untouchedNewCells.has(cell2Id)).toBe(true);

      // Move cell1 to the end
      actions.moveCell({
        cellId: cell1Id,
        before: false,
      });

      // Both cells should still be untouched
      expect(state.untouchedNewCells.has(cell1Id)).toBe(true);
      expect(state.untouchedNewCells.has(cell2Id)).toBe(true);
    });

    it("does not remove untouched state when cell is deleted", () => {
      // We could implement this, but it doesn't actually affect downstream behavior.
      // It is easier to leave it, so `undo` works as expected.

      // Create a cell with hideCode
      actions.createNewCell({
        cellId: "__end__",
        before: false,
        hideCode: true,
      });

      const newCellId =
        state.cellIds.inOrderIds[state.cellIds.inOrderIds.length - 1];
      expect(state.untouchedNewCells.has(newCellId)).toBe(true);

      // Delete the cell
      actions.deleteCell({ cellId: newCellId });

      // Does not actually remove untouched state
      expect(state.untouchedNewCells.has(newCellId)).toBe(true);
    });

    it("restores untouched state when cell deletion is undone", () => {
      // Create a cell with hideCode
      actions.createNewCell({
        cellId: "__end__",
        before: false,
        hideCode: true,
      });

      const newCellId =
        state.cellIds.inOrderIds[state.cellIds.inOrderIds.length - 1];
      expect(state.untouchedNewCells.has(newCellId)).toBe(true);

      // Delete the cell
      actions.deleteCell({ cellId: newCellId });
      // Still exists in untouchedNewCells
      expect(state.untouchedNewCells.has(newCellId)).toBe(true);

      // Undo the deletion
      actions.undoDeleteCell();

      // The cell should be restored but no longer untouched
      // (this is expected behavior - undoing doesn't restore untouched state)
      const restoredCellId =
        state.cellIds.inOrderIds[state.cellIds.inOrderIds.length - 1];
      expect(state.untouchedNewCells.has(restoredCellId)).toBe(false);
    });

    it("untouched cell behavior with hide_code config", () => {
      // Create a cell with hideCode and hide_code config
      actions.createNewCell({
        cellId: "__end__",
        before: false,
        hideCode: true,
      });

      const newCellId =
        state.cellIds.inOrderIds[state.cellIds.inOrderIds.length - 1];

      // Update the cell config to hide code
      actions.updateCellConfig({
        cellId: newCellId,
        config: { hide_code: true },
      });

      // Cell should be untouched and have hide_code config
      expect(state.untouchedNewCells.has(newCellId)).toBe(true);
      expect(state.cellData[newCellId].config.hide_code).toBe(true);

      // Code should not be hidden because cell is untouched
      expect(exportedForTesting.isCellCodeHidden(state, newCellId)).toBe(false);

      // Mark as touched
      actions.markTouched({ cellId: newCellId });

      // Now code should be hidden
      expect(state.untouchedNewCells.has(newCellId)).toBe(false);
      expect(exportedForTesting.isCellCodeHidden(state, newCellId)).toBe(true);
    });
  });
});

describe("isCellCodeHidden", () => {
  const state = initialNotebookState();
  const firstCellId = state.cellIds.inOrderIds[0];

  it("returns false when hide_code is false and cell is not untouched", () => {
    const testCellId = "test-cell" as CellId;
    const testState: NotebookState = {
      ...state,
      cellData: {
        ...state.cellData,
        [testCellId]: {
          ...state.cellData[firstCellId],
          id: testCellId,
          config: { hide_code: false, disabled: false, column: null },
        },
      },
      untouchedNewCells: new Set(),
    };

    expect(exportedForTesting.isCellCodeHidden(testState, testCellId)).toBe(
      false,
    );
  });

  it("returns true when hide_code is true and cell is not untouched", () => {
    const testCellId = "test-cell" as CellId;
    const testState: NotebookState = {
      ...state,
      cellData: {
        ...state.cellData,
        [testCellId]: {
          ...state.cellData[firstCellId],
          id: testCellId,
          config: { hide_code: true, disabled: false, column: null },
        },
      },
      untouchedNewCells: new Set(),
    };

    expect(exportedForTesting.isCellCodeHidden(testState, testCellId)).toBe(
      true,
    );
  });

  it("returns false when hide_code is true but cell is untouched", () => {
    const testCellId = "test-cell" as CellId;
    const testState: NotebookState = {
      ...state,
      cellData: {
        ...state.cellData,
        [testCellId]: {
          ...state.cellData[firstCellId],
          id: testCellId,
          config: { hide_code: true, disabled: false, column: null },
        },
      },
      untouchedNewCells: new Set([testCellId]),
    };

    expect(exportedForTesting.isCellCodeHidden(testState, testCellId)).toBe(
      false,
    );
  });

  it("returns false when hide_code is false and cell is untouched", () => {
    const testCellId = "test-cell" as CellId;
    const testState: NotebookState = {
      ...state,
      cellData: {
        ...state.cellData,
        [testCellId]: {
          ...state.cellData[firstCellId],
          id: testCellId,
          config: { hide_code: false, disabled: false, column: null },
        },
      },
      untouchedNewCells: new Set([testCellId]),
    };

    expect(exportedForTesting.isCellCodeHidden(testState, testCellId)).toBe(
      false,
    );
  });
});
