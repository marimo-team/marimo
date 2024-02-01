/* Copyright 2024 Marimo. All rights reserved. */
import { afterAll, beforeAll, beforeEach, describe, expect, it } from "vitest";
import {
  NotebookState,
  exportedForTesting,
  flattenNotebookCells,
  notebookCells,
} from "../cells";
import { CellId } from "@/core/cells/ids";
import { OutputMessage } from "@/core/kernel/messages";
import { Seconds } from "@/utils/time";

const { initialNotebookState, reducer, createActions } = exportedForTesting;

function formatCells(notebook: NotebookState) {
  const cells = notebookCells(notebook);
  return `\n${cells
    .map((cell) => [`key: ${cell.id}`, `code: '${cell.code}'`].join("\n"))
    .join("\n\n")}`;
}

describe("cell reducer", () => {
  let state: NotebookState;
  let cells: ReturnType<typeof flattenNotebookCells>;
  let firstCellId: CellId;

  const actions = createActions((action) => {
    state = reducer(state, action);
    cells = flattenNotebookCells(state);
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
    actions.createNewCell({ cellId: undefined!, before: false });
    firstCellId = state.cellIds[0];
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
      key: 0
      code: ''

      key: 1
      code: ''"
    `);
  });

  it("can add a cell before another cell", () => {
    actions.createNewCell({
      cellId: firstCellId,
      before: true,
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      key: 1
      code: ''

      key: 0
      code: ''"
    `);
  });

  it("can delete a cell", () => {
    actions.createNewCell({
      cellId: firstCellId,
      before: false,
    });
    actions.deleteCell({
      cellId: firstCellId,
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      key: 1
      code: ''"
    `);

    // undo
    actions.undoDeleteCell();
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      key: 2
      code: ''

      key: 1
      code: ''"
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
      key: 0
      code: 'import numpy as np'"
    `);
  });

  it("can move a cell", () => {
    actions.createNewCell({
      cellId: firstCellId,
      before: false,
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      key: 0
      code: ''

      key: 1
      code: ''"
    `);

    // move first cell to the end
    actions.moveCell({
      cellId: firstCellId,
      before: false,
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      key: 1
      code: ''

      key: 0
      code: ''"
    `);

    // move it back
    actions.moveCell({
      cellId: firstCellId,
      before: true,
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      key: 0
      code: ''

      key: 1
      code: ''"
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
      key: 0
      code: ''

      key: 1
      code: ''

      key: 2
      code: ''"
    `);

    // drag first cell to the end
    actions.dropCellOver({
      cellId: firstCellId,
      overCellId: "2" as CellId,
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      key: 1
      code: ''

      key: 2
      code: ''

      key: 0
      code: ''"
    `);

    // drag it back to the middle
    actions.dropCellOver({
      cellId: firstCellId,
      overCellId: "2" as CellId,
    });
    expect(formatCells(state)).toMatchInlineSnapshot(`
      "
      key: 1
      code: ''

      key: 0
      code: ''

      key: 2
      code: ''"
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
    expect(cell.status).toBe("idle");
    expect(cell.lastCodeRun).toBe("import marimo as mo");
    expect(cell.edited).toBe(false);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Receive queued messages
    actions.handleCellMessage({
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: null,
        status: "queued",
        timestamp: new Date(10).getTime() as Seconds,
      },
    });
    cell = cells[0];
    expect(cell.status).toBe("queued");
    expect(cell.lastCodeRun).toBe("import marimo as mo");
    expect(cell.edited).toBe(false);
    expect(cell.runElapsedTimeMs).toBe(null);
    expect(cell.runStartTimestamp).toBe(null);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Receive running messages
    actions.handleCellMessage({
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: null,
        status: "running",
        timestamp: new Date(20).getTime() as Seconds,
      },
    });
    cell = cells[0];
    expect(cell.status).toBe("running");
    expect(cell.lastCodeRun).toBe("import marimo as mo");
    expect(cell.edited).toBe(false);
    expect(cell.runElapsedTimeMs).toBe(null);
    expect(cell.runStartTimestamp).toBe(20);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Console messages shouldn't transition status
    actions.handleCellMessage({
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: {
          channel: "stdout",
          mimetype: "text/plain",
          data: "hello!",
          timestamp: 0,
        },
        status: null,
        timestamp: new Date(22).getTime() as Seconds,
      },
    });
    cell = cells[0];
    expect(cell.status).toBe("running");
    expect(cell.edited).toBe(false);
    expect(cell.runElapsedTimeMs).toBe(null);
    expect(cell.runStartTimestamp).toBe(20);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Receive output messages
    actions.handleCellMessage({
      cellId: firstCellId,
      message: {
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
        timestamp: new Date(33).getTime() as Seconds,
      },
    });
    cell = cells[0];
    expect(cell.status).toBe("idle");
    expect(cell.edited).toBe(false);
    expect(cell.runElapsedTimeMs).toBe(13_000);
    expect(cell.runStartTimestamp).toBe(null);
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
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: null,
        status: "queued",
        timestamp: new Date(40).getTime() as Seconds,
      },
    });
    cell = cells[0];
    expect(cell.output).not.toBe(null); // keep old output
    // Running
    actions.handleCellMessage({
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: null,
        status: "running",
        timestamp: new Date(50).getTime() as Seconds,
      },
    });
    cell = cells[0];
    expect(cell.output).not.toBe(null); // keep old output
    // Receive error
    actions.handleCellMessage({
      cellId: firstCellId,
      message: {
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
        timestamp: new Date(61).getTime() as Seconds,
      },
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
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: null,
        status: "queued",
        timestamp: new Date(40).getTime() as Seconds,
      },
    });
    cell = cells[0];
    expect(cell.output).not.toBe(null); // keep old output
    // Running
    actions.handleCellMessage({
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: null,
        status: "running",
        timestamp: new Date(50).getTime() as Seconds,
      },
    });
    cell = cells[0];
    expect(cell.output).not.toBe(null); // keep old output
    // Receive error
    actions.handleCellMessage({
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: {
          channel: "marimo-error",
          mimetype: "application/vnd.marimo+error",
          data: [{ type: "interruption" }],
          timestamp: 0,
        },
        console: null,
        status: "idle",
        timestamp: new Date(61).getTime() as Seconds,
      },
    });
    cell = cells[0];
    expect(cell.status).toBe("idle");
    expect(cell.lastCodeRun).toBe(cell.code);
    expect(cell.edited).toBe(false);
    expect(cell.runElapsedTimeMs).toBe(11_000);
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
      cellId: secondCell,
      message: {
        cell_id: secondCell,
        output: null,
        console: null,
        status: "queued",
        timestamp: new Date(10).getTime() as Seconds,
      },
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
      cellId: secondCell,
      message: {
        cell_id: secondCell,
        output: null,
        console: null,
        status: "stale",
        timestamp: new Date(20).getTime() as Seconds,
      },
    });
    cell = cells[1];
    expect(cell.status).toBe("stale");
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
      cellId: firstCellId,
      message: {
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
        timestamp: new Date(33).getTime() as Seconds,
      },
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
    expect(cell.config).toEqual({});

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
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: null,
        status: "queued",
        timestamp: new Date(10).getTime() as Seconds,
      },
    });
    let cell = cells[0];
    expect(cell.status).toBe("queued");
    expect(cell.lastCodeRun).toBe(
      "mo.md('This has an ancestor that was stopped')"
    );
    expect(cell.edited).toBe(false);
    expect(cell.runElapsedTimeMs).toBe(null);
    expect(cell.runStartTimestamp).toBe(null);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Receive idle message
    actions.handleCellMessage({
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: null,
        status: "idle",
        timestamp: new Date(20).getTime() as Seconds,
      },
    });
    cell = cells[0];
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Receive stop output
    actions.handleCellMessage({
      cellId: firstCellId,
      message: {
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
        timestamp: new Date(20).getTime() as Seconds,
      },
    });
    cell = cells[0];
    expect(cell.status).toBe("idle");
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect((cell.output?.data as any)[0].msg).toBe(
      "This cell wasn't run because an ancestor was stopped with `mo.stop`: "
    );
    expect(cell.stopped).toBe(true);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Receive queued message
    actions.handleCellMessage({
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: null,
        status: "queued",
        timestamp: new Date(30).getTime() as Seconds,
      },
    });
    cell = cells[0];
    expect(cell.status).toBe("queued");
    expect(cell.stopped).toBe(true);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Receive running message
    actions.handleCellMessage({
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: null,
        status: "running",
        timestamp: new Date(40).getTime() as Seconds,
      },
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
    expect(cell.status).toBe("idle");
    expect(cell.consoleOutputs).toEqual([]);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Receive queued messages
    actions.handleCellMessage({
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: null,
        status: "queued",
        timestamp: new Date(10).getTime() as Seconds,
      },
    });
    cell = cells[0];
    expect(cell.status).toBe("queued");
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Receive running messages
    actions.handleCellMessage({
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: null,
        status: "running",
        timestamp: new Date(20).getTime() as Seconds,
      },
    });
    cell = cells[0];
    expect(cell.status).toBe("running");
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Add console
    actions.handleCellMessage({
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: STDOUT,
        status: null,
        timestamp: new Date(22).getTime() as Seconds,
      },
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
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: STD_IN_1,
        status: null,
        timestamp: new Date(22).getTime() as Seconds,
      },
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
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: STD_IN_2,
        status: null,
        timestamp: new Date(22).getTime() as Seconds,
      },
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
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: {
          channel: "marimo-error",
          mimetype: "application/vnd.marimo+error",
          data: [{ type: "interruption" }],
          timestamp: 0,
        },
        console: null,
        status: "idle",
        timestamp: new Date(61).getTime() as Seconds,
      },
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
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: [OLD_STDOUT],
        status: null,
        timestamp: new Date(1).getTime() as Seconds,
      },
    });

    // Prepare for run
    actions.prepareForRun({
      cellId: firstCellId,
    });
    cell = cells[0];
    expect(cell.status).toBe("idle");
    expect(cell.consoleOutputs).toEqual([OLD_STDOUT]); // Old stays there until it starts running
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Receive queued messages
    actions.handleCellMessage({
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: null,
        status: "queued",
        timestamp: new Date(10).getTime() as Seconds,
      },
    });
    cell = cells[0];
    expect(cell.status).toBe("queued");
    expect(cell.consoleOutputs).toEqual([OLD_STDOUT]); // Old stays there until it starts running
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Receive running messages
    actions.handleCellMessage({
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: [], // Backend sends an empty array to clearu
        status: "running",
        timestamp: new Date(20).getTime() as Seconds,
      },
    });
    cell = cells[0];
    expect(cell.status).toBe("running");
    expect(cell.consoleOutputs).toEqual([]);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Add console
    actions.handleCellMessage({
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: [STDOUT],
        status: "idle",
        timestamp: new Date(22).getTime() as Seconds,
      },
    });
    cell = cells[0];
    expect(cell.consoleOutputs).toEqual([STDOUT]);
    expect(cell.status).toBe("idle");
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all
  });
});
