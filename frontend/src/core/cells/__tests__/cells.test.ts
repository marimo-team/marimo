/* Copyright 2026 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { createStore } from "jotai";
import {
  afterAll,
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import type { CellHandle } from "@/components/editor/notebook-cell";
import { CellId, SCRATCH_CELL_ID, SETUP_CELL_ID } from "@/core/cells/ids";
import { foldAllBulk, unfoldAllBulk } from "@/core/codemirror/editing/commands";
import { adaptiveLanguageConfiguration } from "@/core/codemirror/language/extension";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import type { OutputMessage } from "@/core/kernel/messages";
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
import { exportedForTesting as documentTransactionTestExports } from "../document-changes";
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

  const actions = createActions((action) => {
    state = reducer(state, action);
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
  });

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
    actions.createNewCell({ cellId: "__end__", before: false });
    firstCellId = state.cellIds.inOrderIds[0];
  });

  afterEach(() => {
    documentTransactionTestExports.cancelPendingChanges();
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

  it("can add a cell with name and config", () => {
    actions.createNewCell({
      cellId: firstCellId,
      before: false,
      code: "x = 1",
      name: "My Cell",
      config: { hide_code: true, disabled: false },
    });
    const newCellId = state.cellIds.inOrderIds[1];
    expect(state.cellData[newCellId].name).toBe("My Cell");
    expect(state.cellData[newCellId].config.hide_code).toBe(true);
    expect(state.cellData[newCellId].config.disabled).toBe(false);
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

    // Verify scrollKey is set to the restored cell
    expect(state.scrollKey).toBe("2");
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

  it("undo delete restores cell config (hide_code, disabled)", () => {
    actions.createNewCell({
      cellId: firstCellId,
      before: false,
      code: "x = 1",
    });
    const newCellId = state.cellIds.getColumns()[0].atOrThrow(1);

    // Set config to hidden and disabled
    actions.updateCellConfig({
      cellId: newCellId,
      config: { hide_code: true, disabled: true },
    });
    expect(state.cellData[newCellId].config.hide_code).toBe(true);
    expect(state.cellData[newCellId].config.disabled).toBe(true);

    // Delete the cell
    actions.deleteCell({ cellId: newCellId });
    expect(state.cellIds.inOrderIds).not.toContain(newCellId);

    // Undo delete
    actions.undoDeleteCell();
    const restoredCellId =
      state.cellIds.inOrderIds[state.cellIds.inOrderIds.length - 1];

    // Config should be preserved
    expect(state.cellData[restoredCellId].config.hide_code).toBe(true);
    expect(state.cellData[restoredCellId].config.disabled).toBe(true);
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
    actions.addColumnBreakpoint({ cellId: cellId("1") });
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
      cellId: cellId("1"),
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
      cellId: cellId("1"),
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
      overCellId: cellId("2"),
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
      overCellId: cellId("2"),
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [1] ''

      [0] ''

      [2] ''
      "
    `);
  });

  it("can move a cell to an exact index within a column", () => {
    actions.createNewCell({
      cellId: firstCellId,
      before: false,
    });
    actions.createNewCell({
      cellId: cellId("1"),
      before: false,
    });

    const columnId = state.cellIds.atOrThrow(0).id;
    actions.moveCellToIndex({
      cellId: firstCellId,
      columnId,
      index: 3,
    });

    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [1] ''

      [2] ''

      [0] ''
      "
    `);
  });

  it("can move a cell to an exact index across columns", () => {
    actions.createNewCell({
      cellId: firstCellId,
      before: false,
    });
    actions.createNewCell({
      cellId: cellId("1"),
      before: false,
    });
    actions.addColumnBreakpoint({ cellId: cellId("1") });

    const secondColumnId = state.cellIds.atOrThrow(1).id;
    actions.moveCellToIndex({
      cellId: firstCellId,
      columnId: secondColumnId,
      index: 1,
    });

    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      > col 0


      > col 1
      [1] ''

      [0] ''

      [2] ''
      "
    `);
  });

  it("moveCellToIndex is a no-op when moving to the same position", () => {
    actions.createNewCell({
      cellId: firstCellId,
      before: false,
    });
    actions.createNewCell({
      cellId: cellId("1"),
      before: false,
    });

    const columnId = state.cellIds.atOrThrow(0).id;
    const before = formatCells(state);

    actions.moveCellToIndex({
      cellId: firstCellId,
      columnId,
      index: 0,
    });

    expect(formatCells(state)).toBe(before);
  });

  it("moveCellToIndex is a no-op for an invalid columnId", () => {
    actions.createNewCell({
      cellId: firstCellId,
      before: false,
    });

    const before = formatCells(state);

    actions.moveCellToIndex({
      cellId: firstCellId,
      columnId: "nonexistent-column" as CellColumnId,
      index: 0,
    });

    expect(formatCells(state)).toBe(before);
  });

  it("can move multiple cells relative to target", () => {
    actions.createNewCell({
      cellId: firstCellId,
      before: false,
    });
    actions.createNewCell({
      cellId: cellId("1"),
      before: false,
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [0] ''

      [1] ''

      [2] ''
      "
    `);

    // Move first two cells after the third
    actions.moveCellsRelativeTo({
      cellIds: [firstCellId, cellId("1")],
      targetCellId: cellId("2"),
      position: "after",
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [2] ''

      [0] ''

      [1] ''
      "
    `);
  });

  it("can undo cut-paste (move with previousPlacements)", () => {
    actions.createNewCell({
      cellId: firstCellId,
      before: false,
    });
    actions.createNewCell({
      cellId: cellId("1"),
      before: false,
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [0] ''

      [1] ''

      [2] ''
      "
    `);

    const col = state.cellIds.findWithId(firstCellId);
    const previousPlacements = [
      {
        columnId: col.id,
        index: col.indexOfOrThrow(
          firstCellId,
        ) as import("@/utils/id-tree").CellIndex,
      },
      {
        columnId: col.id,
        index: col.indexOfOrThrow(
          cellId("1"),
        ) as import("@/utils/id-tree").CellIndex,
      },
    ];

    actions.moveCellsRelativeTo({
      cellIds: [firstCellId, cellId("1")],
      targetCellId: cellId("2"),
      position: "after",
      previousPlacements,
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [2] ''

      [0] ''

      [1] ''
      "
    `);

    actions.undoDeleteCell();
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [0] ''

      [1] ''

      [2] ''
      "
    `);
  });

  it("undo order: cut-paste then delete — first undo restores delete, second undo undoes move", () => {
    actions.createNewCell({
      cellId: firstCellId,
      before: false,
    });
    actions.createNewCell({
      cellId: cellId("1"),
      before: false,
    });

    const col = state.cellIds.findWithId(firstCellId);
    const previousPlacements = [
      {
        columnId: col.id,
        index: col.indexOfOrThrow(
          firstCellId,
        ) as import("@/utils/id-tree").CellIndex,
      },
      {
        columnId: col.id,
        index: col.indexOfOrThrow(
          cellId("1"),
        ) as import("@/utils/id-tree").CellIndex,
      },
    ];

    actions.moveCellsRelativeTo({
      cellIds: [firstCellId, cellId("1")],
      targetCellId: cellId("2"),
      position: "after",
      previousPlacements,
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [2] ''

      [0] ''

      [1] ''
      "
    `);

    actions.deleteCell({ cellId: cellId("2") });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [0] ''

      [1] ''
      "
    `);

    actions.undoDeleteCell();
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [3] ''

      [0] ''

      [1] ''
      "
    `);

    actions.undoDeleteCell();
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [0] ''

      [1] ''

      [3] ''
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
    expect(cell.consoleOutputs[0]).toMatchObject(STDOUT);
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
    expect(cell.consoleOutputs[0]).toMatchObject(STDOUT);
    expect(cell.consoleOutputs[1]).toMatchObject(STD_IN_1);
    expect(cell.status).toBe("running");
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

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
    expect(cell.consoleOutputs).toMatchObject([
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
    expect(cell.consoleOutputs).toMatchObject([
      STDOUT,
      { ...STD_IN_1, response: "Marimo!" },
      { ...STD_IN_2, response: "" },
    ]);
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
    expect(cell.consoleOutputs).toMatchObject([OLD_STDOUT]); // Old stays there until it starts running
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
    expect(cell.consoleOutputs).toMatchObject([OLD_STDOUT]); // Old stays there until it starts running
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
    expect(cell.consoleOutputs).toMatchObject([]);
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
    expect(cell.consoleOutputs).toMatchObject([STDOUT]);
    expect(cell.status).toBe("idle");
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all
  });

  it("can send a cell to the top", () => {
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({ cellId: cellId("1"), before: false });
    actions.sendToTop({ cellId: cellId("2") });
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
    actions.createNewCell({ cellId: cellId("1"), before: false });
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
    actions.createNewCell({ cellId: cellId("1"), before: false });

    actions.focusCell({ cellId: cellId("1"), where: "before" });
    expect(focusAndScrollCellIntoView).toHaveBeenCalledWith(
      expect.objectContaining({
        cellId: cellId("0"),
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
    const newIds = [cellId("3"), cellId("4"), cellId("5")];
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
      ids: [cellId("2")],
      codeIsStale: false,
    });

    expect(state.cellData[cellId("2")].code).toBe("new code");
    expect(state.cellData[cellId("2")].edited).toBe(false);
    expect(state.cellData[cellId("2")].lastCodeRun).toBe("new code");

    actions.setCellCodes({
      codes: ["new code 2"],
      ids: [cellId("9")],
      codeIsStale: true,
    });

    expect(state.cellData[cellId("9")].code).toBe("new code 2");
    expect(state.cellData[cellId("9")].edited).toBe(true);
    expect(state.cellData[cellId("9")].lastCodeRun).toBe(null);
  });

  it("can partial update cell codes", () => {
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({ cellId: cellId("1"), before: false });

    expect(state.cellIds.inOrderIds).toEqual([
      cellId("0"),
      cellId("1"),
      cellId("2"),
    ]);
    expect(state.cellData[cellId("0")].code).toBe("");
    expect(state.cellData[cellId("1")].code).toBe("");
    expect(state.cellData[cellId("2")].code).toBe("");

    // Update cell 1
    actions.setCellCodes({
      codes: ["new code 2"],
      ids: [cellId("1")],
      codeIsStale: false,
    });

    expect(state.cellIds.inOrderIds).toEqual([
      cellId("0"),
      cellId("1"),
      cellId("2"),
    ]);
    expect(state.cellData[cellId("0")].code).toBe("");
    expect(state.cellData[cellId("1")].code).toBe("new code 2");
    expect(state.cellData[cellId("1")].edited).toBe(false);
    expect(state.cellData[cellId("2")].code).toBe("");
  });

  it("can set cell codes with new cell ids, while preserving the old cell data", () => {
    actions.setCellCodes({
      codes: ["code1", "code2", "code3"],
      ids: [cellId("3"), cellId("4"), cellId("5")],
      codeIsStale: false,
    });
    expect(state.cellData[cellId("3")].code).toBe("code1");
    expect(state.cellData[cellId("4")].code).toBe("code2");
    expect(state.cellData[cellId("5")].code).toBe("code3");

    // Update with some new cell ids and some old cell ids
    actions.setCellIds({
      cellIds: [cellId("1"), cellId("2"), cellId("3"), cellId("4")],
    });
    actions.setCellCodes({
      codes: ["new1", "new2", "code1", "code2"],
      ids: [cellId("1"), cellId("2"), cellId("3"), cellId("4")],
      codeIsStale: false,
    });
    expect(state.cellData[cellId("1")].code).toBe("new1");
    expect(state.cellData[cellId("2")].code).toBe("new2");
    expect(state.cellData[cellId("3")].code).toBe("code1");
    expect(state.cellData[cellId("4")].code).toBe("code2");
    expect(state.cellIds.inOrderIds).toEqual([
      cellId("1"),
      cellId("2"),
      cellId("3"),
      cellId("4"),
    ]);
    // Cell 5 data is preserved (possibly used for tracing), but it's not in the cellIds
    expect(state.cellData[cellId("5")]).not.toBeUndefined();
  });

  it("can set cell codes with names and configs", () => {
    const newIds = [cellId("3"), cellId("4")];
    actions.setCellIds({ cellIds: newIds });
    actions.setCellCodes({
      codes: ["code1", "code2"],
      ids: newIds,
      codeIsStale: false,
      names: ["setup_cell", "analysis"],
      configs: [
        { hide_code: true, disabled: false, column: null },
        { hide_code: false, disabled: true, column: null },
      ],
    });

    expect(state.cellData[cellId("3")].name).toBe("setup_cell");
    expect(state.cellData[cellId("3")].config.hide_code).toBe(true);
    expect(state.cellData[cellId("3")].config.disabled).toBe(false);

    expect(state.cellData[cellId("4")].name).toBe("analysis");
    expect(state.cellData[cellId("4")].config.hide_code).toBe(false);
    expect(state.cellData[cellId("4")].config.disabled).toBe(true);
  });

  it("can set cell codes without names/configs (backward compat)", () => {
    const newIds = [cellId("3")];
    actions.setCellIds({ cellIds: newIds });
    actions.setCellCodes({
      codes: ["code1"],
      ids: newIds,
      codeIsStale: false,
    });

    // Should use defaults when names/configs not provided
    expect(state.cellData[cellId("3")].code).toBe("code1");
    expect(state.cellData[cellId("3")].config.hide_code).toBe(false);
    expect(state.cellData[cellId("3")].config.disabled).toBe(false);
  });

  it("can update names and configs on existing cells via setCellCodes", () => {
    // Set initial state
    actions.setCellCodes({
      codes: ["x = 1"],
      ids: [firstCellId],
      codeIsStale: false,
      names: ["old_name"],
      configs: [{ hide_code: false, disabled: false, column: null }],
    });
    expect(state.cellData[firstCellId].name).toBe("old_name");
    expect(state.cellData[firstCellId].config.hide_code).toBe(false);

    // Update with new name and config (same code)
    actions.setCellCodes({
      codes: ["x = 1"],
      ids: [firstCellId],
      codeIsStale: true,
      names: ["new_name"],
      configs: [{ hide_code: true, disabled: false, column: null }],
    });
    expect(state.cellData[firstCellId].name).toBe("new_name");
    expect(state.cellData[firstCellId].config.hide_code).toBe(true);
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
      cellId: cellId("1"),
      before: false,
      code: "# Header",
    });
    actions.createNewCell({
      cellId: cellId("2"),
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
      cellId: cellId("1"),
      before: false,
      code: "# First Column Header",
    });
    actions.createNewCell({
      cellId: cellId("2"),
      before: false,
      code: "## First Column Subheader",
    });

    actions.addColumnBreakpoint({ cellId: cellId("2") });

    actions.createNewCell({
      cellId: cellId("3"),
      before: false,
      code: "# Second Column Header",
    });
    actions.createNewCell({
      cellId: cellId("4"),
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
      cellId: cellId("1"),
      before: false,
      code: "# Header",
    });
    actions.createNewCell({
      cellId: cellId("2"),
      before: false,
      code: "## Subheader",
    });
    actions.createNewCell({
      cellId: cellId("3"),
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
    actions.createNewCell({ cellId: cellId("1"), before: false });
    actions.collapseCell({ cellId: firstCellId });

    actions.showCellIfHidden({ cellId: cellId("1") });
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

  it("can add a column breakpoint", () => {
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({ cellId: cellId("1"), before: false });
    actions.createNewCell({ cellId: cellId("2"), before: false });

    expect(state.cellIds.getColumns().length).toBe(1);
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [0] ''

      [1] ''

      [2] ''

      [3] ''
      "
    `);

    actions.addColumnBreakpoint({ cellId: cellId("2") });

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
    expect(state.cellIds.getColumns()[0].topLevelIds).toEqual([
      cellId("0"),
      cellId("1"),
    ]);
    expect(state.cellIds.getColumns()[1].topLevelIds).toEqual([
      cellId("2"),
      cellId("3"),
    ]);
  });

  it("cannot add a column breakpoint before the first cell", () => {
    expect(state.cellIds.getColumns().length).toBe(1);
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({ cellId: cellId("1"), before: false });
    actions.addColumnBreakpoint({ cellId: firstCellId });
    expect(state.cellIds.getColumns().length).toBe(1);
  });

  it("can delete a column", () => {
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({ cellId: cellId("1"), before: false });
    actions.createNewCell({ cellId: cellId("2"), before: false });
    actions.addColumnBreakpoint({ cellId: cellId("2") });

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
    actions.createNewCell({ cellId: cellId("1"), before: false });

    const initialState = { ...state };

    actions.deleteColumn({ columnId: initialState.cellIds.atOrThrow(0).id });

    // State should not change
    expect(state).toEqual(initialState);
  });

  it("can drop a cell over another cell", () => {
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({ cellId: cellId("1"), before: false });
    actions.createNewCell({ cellId: cellId("2"), before: false });

    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [0] ''

      [1] ''

      [2] ''

      [3] ''
      "
    `);

    actions.dropCellOverCell({
      cellId: cellId("0"),
      overCellId: cellId("3"),
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
    actions.createNewCell({ cellId: cellId("1"), before: false });

    expect(state.cellIds.getColumns().length).toBe(1);
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      [0] ''

      [1] ''

      [2] ''
      "
    `);

    actions.dropOverNewColumn({ cellId: cellId("1") });

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
    expect(state.cellIds.getColumns()[0].topLevelIds).toEqual([
      cellId("0"),
      cellId("2"),
    ]);
    expect(state.cellIds.getColumns()[1].topLevelIds).toEqual([cellId("1")]);
  });

  it("can drop a column over another column", () => {
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({ cellId: cellId("1"), before: false });
    actions.createNewCell({ cellId: cellId("2"), before: false });
    actions.addColumnBreakpoint({ cellId: cellId("2") });

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
    expect(state.cellIds.getColumns()[0].topLevelIds).toEqual([
      cellId("2"),
      cellId("3"),
    ]);
    expect(state.cellIds.getColumns()[1].topLevelIds).toEqual([
      cellId("0"),
      cellId("1"),
    ]);
  });

  it("can compact columns", () => {
    // Create initial state with 3 columns, including an empty one
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({ cellId: cellId("1"), before: false });
    actions.addColumnBreakpoint({ cellId: cellId("1") });
    actions.addColumnBreakpoint({ cellId: cellId("2") });
    actions.dropOverNewColumn({ cellId: cellId("2") });

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
    expect(state.cellIds.getColumns()[0].topLevelIds).toEqual([cellId("0")]);
    expect(state.cellIds.getColumns()[1].topLevelIds).toEqual([cellId("1")]);
    expect(state.cellIds.getColumns()[2].topLevelIds).toEqual([]);
    expect(state.cellIds.getColumns()[3].topLevelIds).toEqual([cellId("2")]);

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
    expect(state.cellIds.getColumns()[0].topLevelIds).toEqual([cellId("0")]);
    expect(state.cellIds.getColumns()[1].topLevelIds).toEqual([cellId("1")]);
    expect(state.cellIds.getColumns()[2].topLevelIds).toEqual([cellId("2")]);
  });

  it("rebuildCellColumns regroups cells by config.column", () => {
    // Create four cells in a single column.
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({ cellId: cellId("1"), before: false });
    actions.createNewCell({ cellId: cellId("2"), before: false });
    expect(state.cellIds.getColumns().length).toBe(1);

    // Explicitly set config.column on each cell. This ONLY updates metadata —
    // updateCellConfig does not touch the MultiColumn tree.
    actions.updateCellConfig({
      cellId: cellId("0"),
      config: { column: 0 },
    });
    actions.updateCellConfig({
      cellId: cellId("2"),
      config: { column: 1 },
    });

    // Tree is still a single column at this point.
    expect(state.cellIds.getColumns().length).toBe(1);

    // Now rebuild the column tree from metadata.
    actions.rebuildCellColumns({
      cellIds: [cellId("0"), cellId("1"), cellId("2"), cellId("3")],
    });

    expect(state.cellIds.getColumns().length).toBe(2);
    // Cell 1 inherits from 0 (col 0), cell 3 inherits from 2 (col 1).
    expect(state.cellIds.getColumns()[0].topLevelIds).toEqual([
      cellId("0"),
      cellId("1"),
    ]);
    expect(state.cellIds.getColumns()[1].topLevelIds).toEqual([
      cellId("2"),
      cellId("3"),
    ]);
  });

  it("rebuildCellColumns with explicit column on every cell", () => {
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({ cellId: cellId("1"), before: false });
    actions.createNewCell({ cellId: cellId("2"), before: false });

    for (const [id, col] of [
      ["0", 1],
      ["1", 0],
      ["2", 1],
      ["3", 0],
    ] as const) {
      actions.updateCellConfig({ cellId: cellId(id), config: { column: col } });
    }

    actions.rebuildCellColumns({
      cellIds: [cellId("0"), cellId("1"), cellId("2"), cellId("3")],
    });

    expect(state.cellIds.getColumns().length).toBe(2);
    expect(state.cellIds.getColumns()[0].topLevelIds).toEqual([
      cellId("1"),
      cellId("3"),
    ]);
    expect(state.cellIds.getColumns()[1].topLevelIds).toEqual([
      cellId("0"),
      cellId("2"),
    ]);
  });

  it("rebuildCellColumns collapses to one column when all cells are col 0", () => {
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.addColumnBreakpoint({ cellId: cellId("1") });
    expect(state.cellIds.getColumns().length).toBe(2);

    // Wipe column metadata back to 0 for both cells.
    actions.updateCellConfig({ cellId: cellId("0"), config: { column: 0 } });
    actions.updateCellConfig({ cellId: cellId("1"), config: { column: 0 } });

    actions.rebuildCellColumns({
      cellIds: [cellId("0"), cellId("1")],
    });

    expect(state.cellIds.getColumns().length).toBe(1);
    expect(state.cellIds.getColumns()[0].topLevelIds).toEqual([
      cellId("0"),
      cellId("1"),
    ]);
  });

  it("rebuildCellColumns follows the provided order, not current tree order", () => {
    // Start with a single column.
    actions.createNewCell({ cellId: firstCellId, before: false });
    actions.createNewCell({ cellId: cellId("1"), before: false });
    actions.updateCellConfig({ cellId: cellId("0"), config: { column: 0 } });
    actions.updateCellConfig({ cellId: cellId("2"), config: { column: 1 } });

    // Pass the reversed order. The rebuild should honor it.
    actions.rebuildCellColumns({
      cellIds: [cellId("2"), cellId("1"), cellId("0")],
    });

    // cellIds iteration:
    //   2 → col=1, pushed to col1, prev=1
    //   1 → col=null, pushed to col[prev=1] = col1
    //   0 → col=0, pushed to col0
    expect(state.cellIds.getColumns()[0].topLevelIds).toEqual([cellId("0")]);
    expect(state.cellIds.getColumns()[1].topLevelIds).toEqual([
      cellId("2"),
      cellId("1"),
    ]);
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

  it("can create and noop-update a setup cell", () => {
    // Create the setup cell
    actions.addSetupCellIfDoesntExist({ code: "# Setup code" });

    // Check that setup cell was created
    expect(state.cellData[SETUP_CELL_ID].id).toBe(SETUP_CELL_ID);
    expect(state.cellData[SETUP_CELL_ID].name).toBe("setup");
    expect(state.cellData[SETUP_CELL_ID].code).toBe("# Setup code");
    expect(state.cellData[SETUP_CELL_ID].edited).toBe(true);
    expect(state.cellIds.inOrderIds).toContain(SETUP_CELL_ID);

    // Update the setup cell
    actions.addSetupCellIfDoesntExist({ code: "# Updated setup code" });

    // Check that the setup cell did not change, since it already exists
    expect(state.cellData[SETUP_CELL_ID].code).toBe("# Setup code");
    expect(state.cellData[SETUP_CELL_ID].edited).toBe(true);
    expect(state.cellIds.inOrderIds).toContain(SETUP_CELL_ID);
  });

  it("can delete and undelete the setup cell", () => {
    // Create the setup cell
    actions.addSetupCellIfDoesntExist({ code: "# Setup code" });

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

    // Verify scrollKey is set to the restored setup cell
    expect(state.scrollKey).toBe(SETUP_CELL_ID);
  });

  it("can delete and then create a new setup cell", () => {
    // Create the setup cell
    actions.addSetupCellIfDoesntExist({ code: "# Setup code" });

    // Delete the setup cell
    actions.deleteCell({ cellId: SETUP_CELL_ID });

    // Create a new setup cell
    actions.addSetupCellIfDoesntExist({ code: "# New code" });

    // Check that the new setup cell was created
    expect(state.cellData[SETUP_CELL_ID].id).toBe(SETUP_CELL_ID);
    expect(state.cellData[SETUP_CELL_ID].name).toBe("setup");
    expect(state.cellData[SETUP_CELL_ID].code).toBe("# New code");
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
        cellId: SCRATCH_CELL_ID,
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
      const nonExistentCellId = cellId("non-existent");

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

    it("can mark an existing cell as untouched", () => {
      // Create a cell without hideCode (not in untouchedNewCells)
      actions.createNewCell({
        cellId: "__end__",
        before: false,
        hideCode: false,
      });

      const newCellId =
        state.cellIds.inOrderIds[state.cellIds.inOrderIds.length - 1];
      expect(state.untouchedNewCells.has(newCellId)).toBe(false);

      // Mark it as untouched
      actions.markUntouched({ cellId: newCellId });

      expect(state.untouchedNewCells.has(newCellId)).toBe(true);
    });

    it("markUntouched is idempotent", () => {
      // Create a cell without hideCode
      actions.createNewCell({
        cellId: "__end__",
        before: false,
        hideCode: false,
      });

      const newCellId =
        state.cellIds.inOrderIds[state.cellIds.inOrderIds.length - 1];
      expect(state.untouchedNewCells.has(newCellId)).toBe(false);

      // Mark as untouched multiple times
      actions.markUntouched({ cellId: newCellId });
      actions.markUntouched({ cellId: newCellId });
      actions.markUntouched({ cellId: newCellId });

      expect(state.untouchedNewCells.has(newCellId)).toBe(true);
    });

    it("markUntouched does not affect already untouched cells", () => {
      // Create a cell with hideCode (already in untouchedNewCells)
      actions.createNewCell({
        cellId: "__end__",
        before: false,
        hideCode: true,
      });

      const newCellId =
        state.cellIds.inOrderIds[state.cellIds.inOrderIds.length - 1];
      expect(state.untouchedNewCells.has(newCellId)).toBe(true);

      // Calling markUntouched should not change anything
      actions.markUntouched({ cellId: newCellId });

      expect(state.untouchedNewCells.has(newCellId)).toBe(true);
    });

    it("markTouched and markUntouched can toggle cell state", () => {
      // Create a cell without hideCode
      actions.createNewCell({
        cellId: "__end__",
        before: false,
        hideCode: false,
      });

      const newCellId =
        state.cellIds.inOrderIds[state.cellIds.inOrderIds.length - 1];

      // Initially not untouched
      expect(state.untouchedNewCells.has(newCellId)).toBe(false);

      // Mark as untouched
      actions.markUntouched({ cellId: newCellId });
      expect(state.untouchedNewCells.has(newCellId)).toBe(true);

      // Mark as touched
      actions.markTouched({ cellId: newCellId });
      expect(state.untouchedNewCells.has(newCellId)).toBe(false);

      // Mark as untouched again
      actions.markUntouched({ cellId: newCellId });
      expect(state.untouchedNewCells.has(newCellId)).toBe(true);
    });

    it("markUntouched works for markdown cell conversion scenario", () => {
      // Simulates converting a Python cell to Markdown
      // 1. Create a regular cell (no hideCode)
      actions.createNewCell({
        cellId: "__end__",
        before: false,
        hideCode: false,
      });

      const cellId =
        state.cellIds.inOrderIds[state.cellIds.inOrderIds.length - 1];

      // Cell starts without hide_code and not in untouchedNewCells
      expect(state.cellData[cellId].config.hide_code).toBe(false);
      expect(state.untouchedNewCells.has(cellId)).toBe(false);
      expect(exportedForTesting.isCellCodeHidden(state, cellId)).toBe(false);

      // 2. Convert to markdown: set hide_code and mark as untouched
      actions.updateCellConfig({
        cellId,
        config: { hide_code: true },
      });
      actions.markUntouched({ cellId });

      // Code should NOT be hidden because cell is untouched (user can edit)
      expect(state.cellData[cellId].config.hide_code).toBe(true);
      expect(state.untouchedNewCells.has(cellId)).toBe(true);
      expect(exportedForTesting.isCellCodeHidden(state, cellId)).toBe(false);

      // 3. User blurs the cell (markTouched)
      actions.markTouched({ cellId });

      // Now code should be hidden
      expect(state.untouchedNewCells.has(cellId)).toBe(false);
      expect(exportedForTesting.isCellCodeHidden(state, cellId)).toBe(true);
    });
  });

  describe("releaseCellAtoms", () => {
    it("atom families cache atoms until explicitly removed", () => {
      const { cellDataAtom, cellRuntimeAtom, cellHandleAtom } =
        exportedForTesting;

      actions.createNewCell({ cellId: firstCellId, before: false });
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

    it("cleans up atom family cache when cells are deleted", () => {
      const { cellDataAtom, cellRuntimeAtom, cellHandleAtom } =
        exportedForTesting;

      actions.createNewCell({ cellId: firstCellId, before: false });
      const newCellId = state.cellIds.inOrderIds[1];

      // Access to create cache entries
      const dataAtom1 = cellDataAtom(newCellId);
      const runtimeAtom1 = cellRuntimeAtom(newCellId);
      const handleAtom1 = cellHandleAtom(newCellId);

      // Triggers purge
      actions.deleteCell({ cellId: newCellId });

      // Access again (should be new instances after cleanup)
      const dataAtom2 = cellDataAtom(newCellId);
      const runtimeAtom2 = cellRuntimeAtom(newCellId);
      const handleAtom2 = cellHandleAtom(newCellId);

      expect(dataAtom2).not.toBe(dataAtom1);
      expect(runtimeAtom2).not.toBe(runtimeAtom1);
      expect(handleAtom2).not.toBe(handleAtom1);
    });
  });
});

describe("isCellCodeHidden", () => {
  const state = initialNotebookState();
  const firstCellId = state.cellIds.inOrderIds[0];

  it("returns false when hide_code is false and cell is not untouched", () => {
    const testCellId = cellId("test-cell");
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
    const testCellId = cellId("test-cell");
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
    const testCellId = cellId("test-cell");
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
    const testCellId = cellId("test-cell");
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

describe("setCells snapshot preservation", () => {
  const CELL_A = cellId("A");
  const CELL_B = cellId("B");
  const newCells: CellData[] = [
    {
      id: CELL_A,
      name: "a",
      code: "1",
      edited: false,
      lastCodeRun: null,
      lastExecutionTime: null,
      config: { hide_code: false, disabled: false, column: null },
      serializedEditorState: null,
    },
    {
      id: CELL_B,
      name: "b",
      code: "2",
      edited: false,
      lastCodeRun: null,
      lastExecutionTime: null,
      config: { hide_code: false, disabled: false, column: null },
      serializedEditorState: null,
    },
  ];

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

  beforeEach(async () => {
    const { isWasm } = await import("@/core/wasm/utils");
    vi.mocked(isWasm).mockReturnValue(true);
  });

  it("preserves hydrated output in WASM", () => {
    const next = exportedForTesting.reducer(hydratedState(), {
      type: "setCells",
      payload: newCells,
    });

    expect(next.cellRuntime[CELL_A].output).toMatchObject({
      data: "hydrated-A",
    });
  });

  it("preserves console-only hydration in WASM", () => {
    const next = exportedForTesting.reducer(hydratedState(), {
      type: "setCells",
      payload: newCells,
    });

    expect(next.cellRuntime[CELL_B].consoleOutputs).toHaveLength(1);
    expect(next.cellRuntime[CELL_B].consoleOutputs[0]).toMatchObject({
      data: "hydrated-B-stdout",
    });
  });

  it("resets cells with no prior runtime even in WASM", () => {
    const empty = MockNotebook.notebookState({ cellData: {} });
    const next = exportedForTesting.reducer(empty, {
      type: "setCells",
      payload: newCells,
    });

    expect(next.cellRuntime[CELL_A].output).toBeNull();
    expect(next.cellRuntime[CELL_A].consoleOutputs).toEqual([]);
    expect(next.cellRuntime[CELL_B].output).toBeNull();
    expect(next.cellRuntime[CELL_B].consoleOutputs).toEqual([]);
  });
});
