/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import type {
  CellExecutionView,
  CellFreshness,
  CellRunStatus,
} from "@/core/executions";
import type { CellMessage, OutputMessage } from "@/core/kernel/messages";
import type { Milliseconds, Seconds } from "@/utils/time";
import {
  consoleOutputIsStale,
  outputIsLoading,
  outputIsStale,
  transitionCell,
} from "../cell";
import { createCellRuntimeState } from "../types";

const STATUSES: CellRunStatus[] = ["queued", "running", "idle"];

const NOW = Date.now() as Milliseconds;

const CURRENT: CellFreshness = { sourceChanged: false, inputsChanged: false };
const EDITED: CellFreshness = { sourceChanged: true, inputsChanged: false };
const REPLACED: CellFreshness = { sourceChanged: false, inputsChanged: true };
const BOTH: CellFreshness = { sourceChanged: true, inputsChanged: true };

type View = Pick<
  CellExecutionView,
  "status" | "outcome" | "startedAt" | "rendered"
>;

function view(overrides: Partial<View>): View {
  return {
    status: "idle",
    outcome: null,
    startedAt: null,
    rendered: false,
    ...overrides,
  };
}

describe("outputIsLoading", () => {
  it("should return true if the cell is running", () => {
    expect(outputIsLoading("running")).toBe(true);
  });

  it("should return true if the cell is queued", () => {
    expect(outputIsLoading("queued")).toBe(true);
  });

  it("should return false if the cell is idle", () => {
    expect(outputIsLoading("idle")).toBe(false);
  });
});

describe("outputIsStale", () => {
  it.each(STATUSES)(
    "should return true if the cell is edited and status is %s",
    (status) => {
      expect(outputIsStale(view({ status }), EDITED, true)).toBe(true);
    },
  );

  it("should return true if the cell is loading", () => {
    expect(outputIsStale(view({ status: "running" }), CURRENT, false)).toBe(
      true,
    );
  });

  it("should return false if the cell is running and has shown output", () => {
    const running = view({ status: "running", rendered: true });
    expect(outputIsStale(running, CURRENT, false)).toBe(false);
  });

  it("should return true if the cell has stale inputs", () => {
    expect(outputIsStale(view({}), REPLACED, false)).toBe(true);
  });

  it("should return false if the cell is interrupted", () => {
    expect(
      outputIsStale(view({ outcome: "interrupted" }), CURRENT, false),
    ).toBe(false);
  });

  it("should return false if the cell is idle and not edited", () => {
    expect(outputIsStale(view({}), CURRENT, false)).toBe(false);
  });

  it("should return true if the source changed while editing", () => {
    expect(outputIsStale(view({}), EDITED, true)).toBe(true);
  });

  it("should keep showing the last result of edited source in a read view", () => {
    expect(outputIsStale(view({}), EDITED, false)).toBe(false);
  });

  it("should return true if the cell is queued", () => {
    expect(outputIsStale(view({ status: "queued" }), CURRENT, false)).toBe(
      true,
    );
  });

  it("should return true if the cell is running but no output is received", () => {
    const running = view({ status: "running", startedAt: NOW });
    expect(outputIsStale(running, CURRENT, false)).toBe(true);
  });

  it("should return true if the cell is interrupted and edited since", () => {
    expect(outputIsStale(view({ outcome: "interrupted" }), EDITED, true)).toBe(
      true,
    );
  });

  it("should not dim output the rerun of edited code has already shown", () => {
    const running = view({ status: "running", rendered: true });
    expect(outputIsStale(running, EDITED, true)).toBe(false);
  });

  it("should dim while the rerun of edited code has shown nothing", () => {
    expect(outputIsStale(view({ status: "running" }), EDITED, true)).toBe(true);
  });

  it("should still dim for changed inputs in a read view when the source also changed", () => {
    expect(outputIsStale(view({}), BOTH, false)).toBe(true);
  });
});

describe("consoleOutputIsStale", () => {
  it("is stale while queued, since the run clears the console", () => {
    expect(consoleOutputIsStale(view({ status: "queued" }), CURRENT)).toBe(
      true,
    );
  });

  it("is not stale while the rerun of edited code is producing it", () => {
    expect(consoleOutputIsStale(view({ status: "running" }), EDITED)).toBe(
      false,
    );
  });

  it("is stale once the settled result is outdated", () => {
    expect(consoleOutputIsStale(view({}), EDITED)).toBe(true);
    expect(consoleOutputIsStale(view({}), REPLACED)).toBe(true);
    expect(consoleOutputIsStale(view({}), CURRENT)).toBe(false);
  });

  it("is not stale after an interruption", () => {
    expect(consoleOutputIsStale(view({ outcome: "interrupted" }), EDITED)).toBe(
      false,
    );
  });

  it("should return false if the cell is interrupted but has stale inputs", () => {
    expect(
      outputIsStale(view({ outcome: "interrupted" }), REPLACED, false),
    ).toBe(false);
  });
});

describe("transitionCell serialization", () => {
  function cellMessage(serialization?: string | null): CellMessage {
    return {
      cell_id: "cell-1",
      ...(serialization === undefined ? {} : { serialization }),
    } as CellMessage;
  }

  it("leaves the hint unchanged when serialization is omitted", () => {
    const cell = createCellRuntimeState({ serialization: "Valid" });
    expect(transitionCell(cell, cellMessage()).serialization).toBe("Valid");
  });

  it("clears the hint when serialization is null", () => {
    const cell = createCellRuntimeState({ serialization: "Valid" });
    expect(transitionCell(cell, cellMessage(null)).serialization).toBeNull();
  });

  it("sets the hint when serialization is a string", () => {
    const cell = createCellRuntimeState();
    expect(transitionCell(cell, cellMessage("Valid")).serialization).toBe(
      "Valid",
    );
  });
});

describe("transitionCell console output ids", () => {
  const output = (
    data: string,
    channel: OutputMessage["channel"] = "stdout",
  ): OutputMessage => ({
    channel,
    mimetype: "text/plain",
    data,
    timestamp: 0,
  });

  it("assigns increasing ids to appended outputs", () => {
    let cell = createCellRuntimeState();
    cell = transitionCell(cell, { console: output("a") } as CellMessage);
    cell = transitionCell(cell, {
      console: output("b", "stderr"),
    } as CellMessage);
    expect(cell.consoleOutputs.map((o) => o.id)).toEqual([1, 2]);
  });

  it("continues from the surviving maximum after a collapse", () => {
    let cell = createCellRuntimeState();
    cell = transitionCell(cell, { console: output("a") } as CellMessage);
    cell = transitionCell(cell, { console: output("b") } as CellMessage);
    expect(cell.consoleOutputs.map((o) => o.id)).toEqual([1]);
    cell = transitionCell(cell, {
      console: output("c", "stderr"),
    } as CellMessage);
    expect(cell.consoleOutputs.map((o) => o.id)).toEqual([1, 2]);
  });

  it("assigns ids when the kernel replaces the whole console", () => {
    const cell = transitionCell(createCellRuntimeState(), {
      console: [output("a"), output("b", "stderr")],
    } as CellMessage);
    expect(cell.consoleOutputs.map((o) => o.id)).toEqual([1, 2]);
  });
});

describe("transitionCell stdin resolution", () => {
  describe.each([
    {
      name: "interrupted",
      message: {
        output: {
          channel: "marimo-error",
          mimetype: "application/vnd.marimo+error",
          data: [{ type: "interruption" }],
          timestamp: 1,
        },
      } as CellMessage,
    },
    {
      name: "idle",
      message: { status: "idle" } as CellMessage,
    },
  ])("when $name", ({ message }) => {
    it.each(["text/plain", "text/password"] as const)(
      "preserves a processed %s prompt",
      (mimetype) => {
        const prompt: OutputMessage = {
          channel: "stdin",
          mimetype,
          data: "Enter a value: ",
          timestamp: 0,
        };
        const waiting = transitionCell(createCellRuntimeState(), {
          console: prompt,
        } as CellMessage);
        const resolved = transitionCell(waiting, message);

        expect(resolved.consoleOutputs[0]).toMatchObject({
          ...prompt,
          response: "",
        });
      },
    );

    it.each(["text/plain", "text/password"] as const)(
      "preserves an existing %s response",
      (mimetype) => {
        const prompt = {
          channel: "stdin" as const,
          mimetype,
          data: "Enter a value: ",
          timestamp: 0,
          response: "submitted value",
        };
        const answered = createCellRuntimeState({
          consoleOutputs: [prompt],
        });
        const resolved = transitionCell(answered, message);

        expect(resolved.consoleOutputs).toEqual([prompt]);
      },
    );
  });

  function stdinOutput(): OutputMessage {
    return {
      channel: "stdin",
      mimetype: "text/plain",
      data: "(Pdb) ",
      timestamp: Date.now() as Seconds,
    } as OutputMessage;
  }

  it("resolves a dangling pdb prompt when the cell goes idle", () => {
    // A paused-pdb cell shows an unanswered stdin prompt (the debugger box);
    // once it finishes (e.g. after quitting with `q`), the box is removed.
    const cell = createCellRuntimeState({
      debuggerActive: true,
      consoleOutputs: [stdinOutput()],
    });
    const next = transitionCell(cell, {
      cell_id: "cell-1",
      status: "idle",
    } as CellMessage);
    expect(next.debuggerActive).toBe(false);
    expect(next.consoleOutputs[0].response).toBe("");
  });

  it("leaves an unanswered prompt interactive while still running", () => {
    const cell = createCellRuntimeState({
      consoleOutputs: [stdinOutput()],
    });
    const next = transitionCell(cell, {
      cell_id: "cell-1",
      status: null,
    } as CellMessage);
    expect(next.consoleOutputs[0].response).toBeUndefined();
  });
});
