/* Copyright 2024 Marimo. All rights reserved. */
import { expect, describe, it } from "vitest";
import { outputIsStale } from "../cell";
import { CellStatus } from "../types";
import { OutputMessage } from "@/core/kernel/messages";
import { Seconds } from "@/utils/time";

const STATUSES: CellStatus[] = [
  "queued",
  "running",
  "idle",
  "stale",
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

describe("outputIsStale", () => {
  it.each(STATUSES)(
    "should return true if the cell is edited and status is %s",
    (status) => {
      const cell = {
        status: status,
        output: null,
        runStartTimestamp: null,
        interrupted: false,
      };
      const edited = true;
      expect(outputIsStale(cell, edited)).toBe(true);
    }
  );

  it("should return true if the cell is loading", () => {
    const cell = {
      status: "running" as CellStatus,
      output: null,
      runStartTimestamp: null,
      interrupted: false,
    };
    const edited = false;
    expect(outputIsStale(cell, edited)).toBe(true);
  });

  it("should return false if the cell is running and output is received after run started", () => {
    const cell = {
      status: "running" as CellStatus,
      output: createOutput(),
      runStartTimestamp: (Date.now() - 1000) as Seconds, // Output received after run started
      interrupted: false,
    };
    const edited = false;
    expect(outputIsStale(cell, edited)).toBe(false);
  });

  it("should return true if the cell status is stale", () => {
    const cell = {
      status: "stale" as CellStatus,
      output: null,
      runStartTimestamp: null,
      interrupted: false,
    };
    const edited = false;
    expect(outputIsStale(cell, edited)).toBe(true);
  });

  it("should return false if the cell is interrupted", () => {
    const cell = {
      status: "running" as CellStatus,
      output: null,
      runStartTimestamp: null,
      interrupted: true,
    };
    const edited = false;
    expect(outputIsStale(cell, edited)).toBe(false);
  });

  it("should return true if the cell is running and output is received before run started", () => {
    const cell = {
      status: "running" as CellStatus,
      output: createOutput(),
      runStartTimestamp: (Date.now() + 1000) as Seconds, // Output received before run started
      interrupted: false,
    };
    const edited = false;
    expect(outputIsStale(cell, edited)).toBe(true);
  });

  it("should return false if the cell is idle and output is received", () => {
    const cell = {
      status: "idle" as CellStatus,
      output: createOutput(),
      runStartTimestamp: null,
      interrupted: false,
    };
    const edited = false;
    expect(outputIsStale(cell, edited)).toBe(false);
  });

  it("should return true if the cell is queued", () => {
    const cell = {
      status: "queued" as CellStatus,
      output: null,
      runStartTimestamp: null,
      interrupted: false,
    };
    const edited = false;
    expect(outputIsStale(cell, edited)).toBe(true);
  });

  it("should return true if the cell is running but no output is received", () => {
    const cell = {
      status: "running" as CellStatus,
      output: null,
      runStartTimestamp: Date.now() as Seconds,
      interrupted: false,
    };
    const edited = false;
    expect(outputIsStale(cell, edited)).toBe(true);
  });

  it("should return false if the cell is idle and not edited", () => {
    const cell = {
      status: "idle" as CellStatus,
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
      status: "idle" as CellStatus,
      output: null,
      runStartTimestamp: null,
      interrupted: true,
    };
    const edited = true;
    expect(outputIsStale(cell, edited)).toBe(false);
  });

  it("should return true if the cell is interrupted but has a stale status", () => {
    // We likely don't get in this state since when a cell is interrupted, it's status is set to idle
    const cell = {
      status: "stale" as CellStatus,
      output: null,
      runStartTimestamp: null,
      interrupted: true,
    };
    const edited = false;
    expect(outputIsStale(cell, edited)).toBe(false);
  });
});
