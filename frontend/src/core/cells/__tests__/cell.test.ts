/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import type { CellMessage, OutputMessage } from "@/core/kernel/messages";
import type { RuntimeState } from "@/core/network/types";
import type { Seconds } from "@/utils/time";
import { outputIsLoading, outputIsStale, transitionCell } from "../cell";
import { createCellRuntimeState } from "../types";

const STATUSES: RuntimeState[] = [
  "queued",
  "running",
  "idle",
  "disabled-transitively",
];

function createOutput(): OutputMessage {
  return {
    channel: "output",
    mimetype: "application/json",
    data: {
      foo: "bar",
    },
    timestamp: Date.now(),
  };
}
describe("outputIsLoading", () => {
  it("should return true if the cell is running", () => {
    expect(outputIsLoading("running" as RuntimeState)).toBe(true);
  });

  it("should return true if the cell is queued", () => {
    expect(outputIsLoading("queued" as RuntimeState)).toBe(true);
  });

  it("should return false if the cell is idle", () => {
    expect(outputIsLoading("idle" as RuntimeState)).toBe(false);
  });

  it("should return false if the cell is disabled-transitively", () => {
    expect(outputIsLoading("disabled-transitively" as RuntimeState)).toBe(
      false,
    );
  });
});

describe("outputIsStale", () => {
  it.each(
    STATUSES,
  )("should return true if the cell is edited and status is %s", (status) => {
    const cell = {
      status: status,
      staleInputs: true,
      output: null,
      runStartTimestamp: null,
      interrupted: false,
    };
    const edited = true;
    expect(outputIsStale(cell, edited)).toBe(true);
  });

  it("should return true if the cell is loading", () => {
    const cell = {
      status: "running" as RuntimeState,
      staleInputs: false,
      output: null,
      runStartTimestamp: null,
      interrupted: false,
    };
    const edited = false;
    expect(outputIsStale(cell, edited)).toBe(true);
  });

  it("should return false if the cell is running and output is received after run started", () => {
    const cell = {
      status: "running" as RuntimeState,
      staleInputs: false,
      output: createOutput(),
      runStartTimestamp: (Date.now() - 1000) as Seconds, // Output received after run started
      interrupted: false,
    };
    const edited = false;
    expect(outputIsStale(cell, edited)).toBe(false);
  });

  it("should return true if the cell status is stale", () => {
    const cell = {
      status: "disabled-transitively" as RuntimeState,
      staleInputs: true,
      output: null,
      runStartTimestamp: null,
      interrupted: false,
    };
    const edited = false;
    expect(outputIsStale(cell, edited)).toBe(true);
  });

  it("should return false if the cell is interrupted", () => {
    const cell = {
      status: "running" as RuntimeState,
      staleInputs: false,
      output: null,
      runStartTimestamp: null,
      interrupted: true,
    };
    const edited = false;
    expect(outputIsStale(cell, edited)).toBe(false);
  });

  it("should return true if the cell is running and output is received before run started", () => {
    const cell = {
      status: "running" as RuntimeState,
      staleInputs: false,
      output: createOutput(),
      runStartTimestamp: (Date.now() + 1000) as Seconds, // Output received before run started
      interrupted: false,
    };
    const edited = false;
    expect(outputIsStale(cell, edited)).toBe(true);
  });

  it("should return false if the cell is idle and output is received", () => {
    const cell = {
      status: "idle" as RuntimeState,
      staleInputs: false,
      output: createOutput(),
      runStartTimestamp: null,
      interrupted: false,
    };
    const edited = false;
    expect(outputIsStale(cell, edited)).toBe(false);
  });

  it("should return true if the cell is queued", () => {
    const cell = {
      status: "queued" as RuntimeState,
      staleInputs: false,
      output: null,
      runStartTimestamp: null,
      interrupted: false,
    };
    const edited = false;
    expect(outputIsStale(cell, edited)).toBe(true);
  });

  it("should return true if the cell is running but no output is received", () => {
    const cell = {
      status: "running" as RuntimeState,
      staleInputs: false,
      output: null,
      runStartTimestamp: Date.now() as Seconds,
      interrupted: false,
    };
    const edited = false;
    expect(outputIsStale(cell, edited)).toBe(true);
  });

  it("should return false if the cell is idle and not edited", () => {
    const cell = {
      status: "idle" as RuntimeState,
      staleInputs: false,
      output: null,
      runStartTimestamp: null,
      interrupted: false,
    };
    const edited = false;
    expect(outputIsStale(cell, edited)).toBe(false);
  });

  it("should return false if the cell is interrupted but also edited", () => {
    // We likely don't get in this state since before a cell is interrupted, it is run and we remove the edited state
    const cell = {
      status: "idle" as RuntimeState,
      staleInputs: false,
      output: null,
      runStartTimestamp: null,
      interrupted: true,
    };
    const edited = true;
    expect(outputIsStale(cell, edited)).toBe(false);
  });

  it("should return true if the cell is interrupted but has a stale status", () => {
    const cell = {
      status: "disabled-transitively" as RuntimeState,
      staleInputs: true,
      output: null,
      runStartTimestamp: null,
      interrupted: true,
    };
    const edited = false;
    expect(outputIsStale(cell, edited)).toBe(false);
  });
});

describe("transitionCell cache handling", () => {
  it("should set cache to 'hit' when message has cache: 'hit'", () => {
    const cell = createCellRuntimeState();
    const message: CellMessage = {
      cell_id: "0",
      status: null,
      output: null,
      console: null,
      stale_inputs: null,
      timestamp: undefined,
      cache: "hit" as const,
    };
    const nextCell = transitionCell(cell, message);
    expect(nextCell.cache).toBe("hit");
  });

  it("should set cache to 'cached' when message has cache: 'cached'", () => {
    const cell = createCellRuntimeState();
    const message: CellMessage = {
      cell_id: "0",
      status: null,
      output: null,
      console: null,
      stale_inputs: null,
      timestamp: undefined,
      cache: "cached" as const,
    };
    const nextCell = transitionCell(cell, message);
    expect(nextCell.cache).toBe("cached");
  });

  it("should preserve cache state when message has cache: null (due to ?? operator)", () => {
    const cell = createCellRuntimeState({ cache: "hit" });
    const message: CellMessage = {
      cell_id: "0",
      status: null,
      output: null,
      console: null,
      stale_inputs: null,
      timestamp: undefined,
      cache: null,
    };
    const nextCell = transitionCell(cell, message);
    // Due to the ?? operator in cell.ts line 77, cache: null preserves existing cache
    expect(nextCell.cache).toBe("hit");
  });

  it("should preserve existing cache state when message does not include cache", () => {
    const cell = createCellRuntimeState({ cache: "hit" });
    const message: CellMessage = {
      cell_id: "0",
      status: null,
      output: null,
      console: null,
      stale_inputs: null,
      timestamp: undefined,
    };
    const nextCell = transitionCell(cell, message);
    expect(nextCell.cache).toBe("hit");
  });

  it("should update cache state when transitioning from hit to cached", () => {
    const cell = createCellRuntimeState({ cache: "hit" });
    const message: CellMessage = {
      cell_id: "0",
      status: null,
      output: null,
      console: null,
      stale_inputs: null,
      timestamp: undefined,
      cache: "cached" as const,
    };
    const nextCell = transitionCell(cell, message);
    expect(nextCell.cache).toBe("cached");
  });

  it("should update cache state when transitioning from cached to hit", () => {
    const cell = createCellRuntimeState({ cache: "cached" });
    const message: CellMessage = {
      cell_id: "0",
      status: null,
      output: null,
      console: null,
      stale_inputs: null,
      timestamp: undefined,
      cache: "hit" as const,
    };
    const nextCell = transitionCell(cell, message);
    expect(nextCell.cache).toBe("hit");
  });

  it("should preserve cache state when message cache is null (due to ?? operator)", () => {
    const cell = createCellRuntimeState({ cache: "cached" });
    const message: CellMessage = {
      cell_id: "0",
      status: null,
      output: null,
      console: null,
      stale_inputs: null,
      timestamp: undefined,
      cache: null,
    };
    const nextCell = transitionCell(cell, message);
    // Due to the ?? operator in cell.ts line 77, cache: null preserves existing cache
    expect(nextCell.cache).toBe("cached");
  });

  it("should handle cache state alongside status transitions", () => {
    const cell = createCellRuntimeState({ status: "idle" });
    const message: CellMessage = {
      cell_id: "0",
      status: "running" as RuntimeState,
      output: null,
      console: null,
      stale_inputs: null,
      timestamp: Date.now() as Seconds,
      cache: "hit" as const,
    };
    const nextCell = transitionCell(cell, message);
    expect(nextCell.cache).toBe("hit");
    expect(nextCell.status).toBe("running");
  });

  it("should handle cache state alongside output updates", () => {
    const cell = createCellRuntimeState();
    const output = createOutput();
    const message: CellMessage = {
      cell_id: "0",
      status: null,
      output: output,
      console: null,
      stale_inputs: null,
      timestamp: undefined,
      cache: "cached" as const,
    };
    const nextCell = transitionCell(cell, message);
    expect(nextCell.cache).toBe("cached");
    expect(nextCell.output).toBe(output);
  });
});
