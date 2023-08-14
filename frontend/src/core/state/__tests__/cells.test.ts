/* Copyright 2023 Marimo. All rights reserved. */
import { beforeEach, describe, expect, it } from "vitest";
import { CellState, createCell } from "../../model/cells";
import { CellsAndHistory, exportedForTesting } from "../cells";
import { CellId } from "@/core/model/ids";

const { initialCellState, reducer } = exportedForTesting;

function formatCells(cells: CellState[]) {
  return `\n${cells
    .map((cell) => [`key: ${cell.key}`, `code: '${cell.code}'`].join("\n"))
    .join("\n\n")}`;
}

describe("cell reducer", () => {
  let state: CellsAndHistory;
  let firstCellKey: CellId;

  beforeEach(() => {
    CellId.reset();

    state = initialCellState();
    state.present = [createCell({ key: CellId.create() })];
    firstCellKey = state.present[0].key;
  });

  it("can add a cell after another cell", () => {
    state = reducer(state, {
      type: "CREATE_CELL",
      cellKey: firstCellKey,
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
    state = reducer(state, {
      type: "CREATE_CELL",
      cellKey: firstCellKey,
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
    state = reducer(state, {
      type: "CREATE_CELL",
      cellKey: firstCellKey,
      before: false,
    });
    state = reducer(state, {
      type: "DELETE_CELL",
      cellKey: firstCellKey,
    });
    expect(formatCells(state.present)).toMatchInlineSnapshot(`
      "
      key: 1
      code: ''"
    `);

    // undo
    state = reducer(state, { type: "UNDO_DELETE_CELL" });
    expect(formatCells(state.present)).toMatchInlineSnapshot(`
      "
      key: 2
      code: ''

      key: 1
      code: ''"
    `);
  });

  it("can update a cell", () => {
    state = reducer(state, {
      type: "UPDATE_CELL_CODE",
      cellKey: firstCellKey,
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
    state = reducer(state, {
      type: "CREATE_CELL",
      cellKey: firstCellKey,
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
    state = reducer(state, {
      type: "MOVE_CELL",
      cellKey: firstCellKey,
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
    state = reducer(state, {
      type: "MOVE_CELL",
      cellKey: firstCellKey,
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
    state = reducer(state, {
      type: "CREATE_CELL",
      cellKey: firstCellKey,
      before: false,
    });
    state = reducer(state, {
      type: "CREATE_CELL",
      cellKey: "1" as CellId,
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
    state = reducer(state, {
      type: "DROP_CELL_OVER",
      cellKey: firstCellKey,
      overCellKey: "2" as CellId,
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
    state = reducer(state, {
      type: "DROP_CELL_OVER",
      cellKey: firstCellKey,
      overCellKey: "2" as CellId,
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
    state = reducer(state, {
      type: "UPDATE_CELL_CODE",
      cellKey: firstCellKey,
      code: "import marimo as mo",
      formattingChange: false,
    });
    cell = state.present[0];
    expect(cell.status).toBe("idle");
    expect(cell.lastCodeRun).toBe(null);
    expect(cell.edited).toBe(true);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Prepare for run
    state = reducer(state, {
      type: "PREPARE_FOR_RUN",
      cellKey: firstCellKey,
    });
    cell = state.present[0];
    expect(cell.status).toBe("idle");
    expect(cell.lastCodeRun).toBe("import marimo as mo");
    expect(cell.edited).toBe(false);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Receive queued messages
    state = reducer(state, {
      type: "HANDLE_CELL_MESSAGE",
      cellKey: firstCellKey,
      message: {
        cell_id: firstCellKey,
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
    state = reducer(state, {
      type: "HANDLE_CELL_MESSAGE",
      cellKey: firstCellKey,
      message: {
        cell_id: firstCellKey,
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
    state = reducer(state, {
      type: "HANDLE_CELL_MESSAGE",
      cellKey: firstCellKey,
      message: {
        cell_id: firstCellKey,
        output: null,
        console: {
          channel: "console",
          mimetype: "text/plain",
          data: "hello!",
          timestamp: "",
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
    state = reducer(state, {
      type: "HANDLE_CELL_MESSAGE",
      cellKey: firstCellKey,
      message: {
        cell_id: firstCellKey,
        output: {
          channel: "output",
          mimetype: "text/plain",
          data: "ok",
          timestamp: "",
        },
        console: {
          channel: "console",
          mimetype: "text/plain",
          data: "hello!",
          timestamp: "",
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
    state = reducer(state, {
      type: "UPDATE_CELL_CODE",
      cellKey: firstCellKey,
      code: "import marimo as mo\nimport numpy",
      formattingChange: false,
    });
    cell = state.present[0];
    expect(cell.status).toBe("idle");
    expect(cell.edited).toBe(true);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Update code should be unedited
    state = reducer(state, {
      type: "UPDATE_CELL_CODE",
      cellKey: firstCellKey,
      code: "import marimo as mo",
      formattingChange: false,
    });
    cell = state.present[0];
    expect(cell.edited).toBe(false);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // Update code should be edited again
    state = reducer(state, {
      type: "UPDATE_CELL_CODE",
      cellKey: firstCellKey,
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
    state = reducer(state, {
      type: "PREPARE_FOR_RUN",
      cellKey: firstCellKey,
    });
    cell = state.present[0];
    expect(cell.output).not.toBe(null); // keep old output
    // Queue
    state = reducer(state, {
      type: "HANDLE_CELL_MESSAGE",
      cellKey: firstCellKey,
      message: {
        cell_id: firstCellKey,
        output: null,
        console: null,
        status: "queued",
        timestamp: new Date(40).getTime(),
      },
    });
    cell = state.present[0];
    expect(cell.output).not.toBe(null); // keep old output
    // Running
    state = reducer(state, {
      type: "HANDLE_CELL_MESSAGE",
      cellKey: firstCellKey,
      message: {
        cell_id: firstCellKey,
        output: null,
        console: null,
        status: "running",
        timestamp: new Date(50).getTime(),
      },
    });
    cell = state.present[0];
    expect(cell.output).not.toBe(null); // keep old output
    // Receive error
    state = reducer(state, {
      type: "HANDLE_CELL_MESSAGE",
      cellKey: firstCellKey,
      message: {
        cell_id: firstCellKey,
        output: {
          channel: "marimo-error",
          mimetype: "application/vnd.marimo+error",
          data: [{ type: "exception", msg: "Oh no!" }],
          timestamp: "",
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
    expect(cell.runElapsedTimeMs).toBe(null);
    expect(cell.runStartTimestamp).toBe(null);
    expect(cell).toMatchSnapshot(); // snapshot everything as a catch all

    // INTERRUPT RESPONSE
    /////////////////
    // Prepare for run
    state = reducer(state, {
      type: "PREPARE_FOR_RUN",
      cellKey: firstCellKey,
    });
    cell = state.present[0];
    expect(cell.output).not.toBe(null); // keep old output
    // Queue
    state = reducer(state, {
      type: "HANDLE_CELL_MESSAGE",
      cellKey: firstCellKey,
      message: {
        cell_id: firstCellKey,
        output: null,
        console: null,
        status: "queued",
        timestamp: new Date(40).getTime(),
      },
    });
    cell = state.present[0];
    expect(cell.output).not.toBe(null); // keep old output
    // Running
    state = reducer(state, {
      type: "HANDLE_CELL_MESSAGE",
      cellKey: firstCellKey,
      message: {
        cell_id: firstCellKey,
        output: null,
        console: null,
        status: "running",
        timestamp: new Date(50).getTime(),
      },
    });
    cell = state.present[0];
    expect(cell.output).not.toBe(null); // keep old output
    // Receive error
    state = reducer(state, {
      type: "HANDLE_CELL_MESSAGE",
      cellKey: firstCellKey,
      message: {
        cell_id: firstCellKey,
        output: {
          channel: "marimo-error",
          mimetype: "application/vnd.marimo+error",
          data: [{ type: "interruption" }],
          timestamp: "",
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

  it("can format code and update cell", () => {
    const firstCellKey = state.present[0].key;
    state = reducer(state, {
      type: "UPDATE_CELL_CODE",
      cellKey: firstCellKey,
      code: "import marimo as    mo",
      formattingChange: false,
    });
    let cell = state.present[0];
    expect(cell.status).toBe("idle");
    expect(cell.lastCodeRun).toBe(null);
    expect(cell.edited).toBe(true);

    // Run
    state = reducer(state, {
      type: "PREPARE_FOR_RUN",
      cellKey: firstCellKey,
    });
    state = reducer(state, {
      type: "HANDLE_CELL_MESSAGE",
      cellKey: firstCellKey,
      message: {
        cell_id: firstCellKey,
        output: {
          channel: "output",
          mimetype: "text/plain",
          data: "ok",
          timestamp: "",
        },
        console: {
          channel: "console",
          mimetype: "text/plain",
          data: "hello!",
          timestamp: "",
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
    state = reducer(state, {
      type: "UPDATE_CELL_CODE",
      cellKey: firstCellKey,
      code: "import marimo as mo",
      formattingChange: true,
    });
    cell = state.present[0];
    expect(cell.status).toBe("idle");
    expect(cell.lastCodeRun).toBe("import marimo as mo");
    expect(cell.edited).toBe(false);
  });
});
