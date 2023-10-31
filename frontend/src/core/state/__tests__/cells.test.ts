/* Copyright 2023 Marimo. All rights reserved. */
import { beforeEach, describe, expect, it } from "vitest";
import { CellState, createCell } from "../../model/cells";
import { CellsAndHistory, exportedForTesting } from "../cells";
import { CellId } from "@/core/model/ids";

const { initialCellState, reducer, createActions } = exportedForTesting;

function formatCells(cells: CellState[]) {
  return `\n${cells
    .map((cell) => [`key: ${cell.key}`, `code: '${cell.code}'`].join("\n"))
    .join("\n\n")}`;
}

describe("cell reducer", () => {
  let state: CellsAndHistory;
  let firstCellId: CellId;

  const actions = createActions((action) => {
    state = reducer(state, action);
  });

  beforeEach(() => {
    CellId.reset();

    state = initialCellState();
    state.present = [createCell({ key: CellId.create() })];
    firstCellId = state.present[0].key;
  });

  it("can add a cell after another cell", () => {
    actions.createNewCell({
      cellId: firstCellId,
      before: false,
    });
    expect(formatCells(state.present)).toMatchInlineSnapshot(`
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
    expect(formatCells(state.present)).toMatchInlineSnapshot(`
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
    expect(formatCells(state.present)).toMatchInlineSnapshot(`
      "
      key: 1
      code: ''"
    `);

    // undo
    actions.undoDeleteCell();
    expect(formatCells(state.present)).toMatchInlineSnapshot(`
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
    expect(formatCells(state.present)).toMatchInlineSnapshot(`
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
    expect(formatCells(state.present)).toMatchInlineSnapshot(`
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
    expect(formatCells(state.present)).toMatchInlineSnapshot(`
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
    expect(formatCells(state.present)).toMatchInlineSnapshot(`
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
    expect(formatCells(state.present)).toMatchInlineSnapshot(`
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
    expect(formatCells(state.present)).toMatchInlineSnapshot(`
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
    expect(formatCells(state.present)).toMatchInlineSnapshot(`
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
    let cell = state.present[0];
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
    cell = state.present[0];
    expect(cell.status).toBe("idle");
    expect(cell.lastCodeRun).toBe(null);
    expect(cell.edited).toBe(true);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Prepare for run
    actions.prepareForRun({
      cellId: firstCellId,
    });
    cell = state.present[0];
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
        timestamp: new Date(10).getTime(),
      },
    });
    cell = state.present[0];
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
        timestamp: new Date(20).getTime(),
      },
    });
    cell = state.present[0];
    expect(cell.status).toBe("running");
    expect(cell.lastCodeRun).toBe("import marimo as mo");
    expect(cell.edited).toBe(false);
    expect(cell.runElapsedTimeMs).toBe(null);
    expect(cell.runStartTimestamp).toBe(20);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Console messags shouldn't transition status
    actions.handleCellMessage({
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: {
          channel: "console",
          mimetype: "text/plain",
          data: "hello!",
          timestamp: 0,
        },
        status: null,
        timestamp: new Date(22).getTime(),
      },
    });
    cell = state.present[0];
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
          channel: "console",
          mimetype: "text/plain",
          data: "hello!",
          timestamp: 0,
        },
        status: "idle",
        timestamp: new Date(33).getTime(),
      },
    });
    cell = state.present[0];
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
    cell = state.present[0];
    expect(cell.status).toBe("idle");
    expect(cell.edited).toBe(true);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Update code should be unedited
    actions.updateCellCode({
      cellId: firstCellId,
      code: "import marimo as mo",
      formattingChange: false,
    });
    cell = state.present[0];
    expect(cell.edited).toBe(false);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Update code should be edited again
    actions.updateCellCode({
      cellId: firstCellId,
      code: "import marimo as mo\nimport numpy",
      formattingChange: false,
    });
    cell = state.present[0];
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
    cell = state.present[0];
    expect(cell.output).not.toBe(null); // keep old output
    // Queue
    actions.handleCellMessage({
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: null,
        status: "queued",
        timestamp: new Date(40).getTime(),
      },
    });
    cell = state.present[0];
    expect(cell.output).not.toBe(null); // keep old output
    // Running
    actions.handleCellMessage({
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: null,
        status: "running",
        timestamp: new Date(50).getTime(),
      },
    });
    cell = state.present[0];
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
        timestamp: new Date(61).getTime(),
      },
    });
    cell = state.present[0];
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
    cell = state.present[0];
    expect(cell.output).not.toBe(null); // keep old output
    // Queue
    actions.handleCellMessage({
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: null,
        status: "queued",
        timestamp: new Date(40).getTime(),
      },
    });
    cell = state.present[0];
    expect(cell.output).not.toBe(null); // keep old output
    // Running
    actions.handleCellMessage({
      cellId: firstCellId,
      message: {
        cell_id: firstCellId,
        output: null,
        console: null,
        status: "running",
        timestamp: new Date(50).getTime(),
      },
    });
    cell = state.present[0];
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
        timestamp: new Date(61).getTime(),
      },
    });
    cell = state.present[0];
    expect(cell.status).toBe("idle");
    expect(cell.lastCodeRun).toBe(null);
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
    const secondCell = state.present[1].key;
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
        timestamp: new Date(10).getTime(),
      },
    });
    let cell = state.present[1];
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
        timestamp: new Date(20).getTime(),
      },
    });
    cell = state.present[1];
    expect(cell.status).toBe("stale");
    expect(cell.lastCodeRun).toBe("mo.slider()");
    expect(cell.edited).toBe(false);
    expect(cell.runElapsedTimeMs).toBe(null);
    expect(cell.runStartTimestamp).toBe(null);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all
  });

  it("can format code and update cell", () => {
    const firstCellId = state.present[0].key;
    actions.updateCellCode({
      cellId: firstCellId,
      code: "import marimo as    mo",
      formattingChange: false,
    });
    let cell = state.present[0];
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
          channel: "console",
          mimetype: "text/plain",
          data: "hello!",
          timestamp: 0,
        },
        status: "idle",
        timestamp: new Date(33).getTime(),
      },
    });

    // Check steady state
    cell = state.present[0];
    expect(cell.status).toBe("idle");
    expect(cell.edited).toBe(false);
    expect(cell.lastCodeRun).toBe("import marimo as    mo");

    // Format code
    actions.updateCellCode({
      cellId: firstCellId,
      code: "import marimo as mo",
      formattingChange: true,
    });
    cell = state.present[0];
    expect(cell.status).toBe("idle");
    expect(cell.lastCodeRun).toBe("import marimo as mo");
    expect(cell.edited).toBe(false);
  });

  it("can update a cells config", () => {
    const firstCellId = state.present[0].key;
    let cell = state.present[0];
    // Starts empty
    expect(cell.config).toEqual({});

    actions.updateCellConfig({
      cellId: firstCellId,
      config: { disabled: true },
    });
    cell = state.present[0];
    expect(cell.config.disabled).toBe(true);

    // Revert
    actions.updateCellConfig({
      cellId: firstCellId,
      config: { disabled: false },
    });
    cell = state.present[0];
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
        timestamp: new Date(10).getTime(),
      },
    });
    let cell = state.present[0];
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
        timestamp: new Date(20).getTime(),
      },
    });
    cell = state.present[0];
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
          timestamp: new Date(20).getTime(),
        },
        console: null,
        status: "idle",
        timestamp: new Date(20).getTime(),
      },
    });
    cell = state.present[0];
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
        timestamp: new Date(30).getTime(),
      },
    });
    cell = state.present[0];
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
        timestamp: new Date(40).getTime(),
      },
    });
    cell = state.present[0];
    expect(cell.status).toBe("running");
    expect(cell.stopped).toBe(false);
    expect(cell.output).toBe(null);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all
  });
});
