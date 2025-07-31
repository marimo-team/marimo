/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import type { OutputMessage } from "@/core/kernel/messages";
import type { RuntimeState } from "@/core/network/types";
import type { Seconds } from "@/utils/time";
import { outputIsLoading, outputIsStale } from "../cell";

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
  it.each(STATUSES)(
    "should return true if the cell is edited and status is %s",
    (status) => {
      const cell = {
        status: status,
        staleInputs: true,
        output: null,
        runStartTimestamp: null,
        interrupted: false,
      };
      const edited = true;
      expect(outputIsStale(cell, edited)).toBe(true);
    },
  );

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
