/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { CellId } from "@/core/cells/ids";
import {
  deriveCellSemanticState,
  deriveOutputStateFromFlags,
  presentCellStatus,
  presentCellState,
  summarizeCellStates,
} from "@/core/cells/semantic-state";
import {
  createCell,
  createCellRuntimeState,
  type CellData,
  type CellRuntimeState,
} from "@/core/cells/types";
import type { Milliseconds, Seconds } from "@/utils/time";

const cellId = CellId.create();
const derive = (
  data: Partial<CellData> = {},
  runtime: Partial<CellRuntimeState> = {},
) =>
  deriveCellSemanticState(
    createCell({ id: cellId, ...data }),
    createCellRuntimeState(runtime),
  );

describe("deriveOutputStateFromFlags", () => {
  it("only treats loading output as updating when the output is stale", () => {
    expect(deriveOutputStateFromFlags(false, true)).toBe("current");
    expect(deriveOutputStateFromFlags(true, true)).toBe("updating");
    expect(deriveOutputStateFromFlags(true, false)).toBe("previous");
  });
});

describe("deriveCellSemanticState", () => {
  it("distinguishes not-run from successful idle cells", () => {
    expect(derive().freshness.kind).toBe("not-run");
    expect(
      derive({}, { runElapsedTimeMs: 10 as Milliseconds }).freshness.kind,
    ).toBe("current");
  });

  it("keeps execution phase independent from outdated inputs", () => {
    const state = derive(
      { edited: true },
      { status: "running", runElapsedTimeMs: 20 as Milliseconds },
    );
    expect(state.phase.kind).toBe("running");
    expect(state.freshness).toEqual({
      kind: "outdated",
      reasons: ["code-edited"],
    });
    expect(presentCellState(state).emphasis).toBe("active");
    expect(state.needsRun).toBe(false);
    expect(state.shouldSchedule).toBe(true);
  });

  it("distinguishes paused cells from cells blocked upstream", () => {
    const paused = derive({
      config: { disabled: true, hide_code: false, column: null },
    });
    const blocked = derive({}, { status: "disabled-transitively" });

    expect(paused.availability.kind).toBe("paused");
    expect(blocked.availability).toEqual({
      kind: "blocked",
      reason: "disabled-ancestor",
    });
  });

  it("only marks actionable changes on unavailable cells", () => {
    const paused = derive(
      {
        lastExecutionTime: 10,
        config: { disabled: true, hide_code: false, column: null },
      },
      { staleInputs: true },
    );
    const blocked = derive(
      {},
      {
        status: "disabled-transitively",
        staleInputs: true,
      },
    );
    const editedBlocked = derive(
      { edited: true },
      { status: "disabled-transitively" },
    );

    expect(paused.needsRun).toBe(false);
    expect(blocked.needsRun).toBe(false);
    expect(editedBlocked.needsRun).toBe(true);
    expect(presentCellState(editedBlocked).showPrimaryAction).toBe(true);
  });

  it("marks old output as updating until the current run emits output", () => {
    const waiting = derive(
      { lastExecutionTime: 10 },
      { status: "running", runStartTimestamp: 20 as Seconds },
    );
    const emitted = derive(
      { lastExecutionTime: 10 },
      {
        status: "running",
        runStartTimestamp: 20 as Seconds,
        output: {
          channel: "output",
          data: "new",
          mimetype: "text/plain",
          timestamp: 21,
        },
      },
    );

    expect(waiting.mainOutput).toBe("updating");
    expect(emitted.mainOutput).toBe("current");
  });

  it("keeps interrupted output current while recommending another run", () => {
    const state = derive(
      { lastExecutionTime: 10 },
      { interrupted: true, runElapsedTimeMs: 20 as Milliseconds },
    );

    expect(state.lastRun.kind).toBe("interrupted");
    expect(state.mainOutput).toBe("current");
    expect(state.needsRun).toBe(true);
  });

  it("keeps an upstream-stopped cell available to run again", () => {
    const state = derive({}, { stopped: true });

    expect(state.availability.kind).toBe("enabled");
    expect(state.lastRun.kind).toBe("stopped");
    expect(presentCellState(state).showPrimaryAction).toBe(true);
  });

  it.each([
    [
      "Paused · Outdated",
      derive(
        {
          edited: true,
          lastExecutionTime: 10,
          config: { disabled: true, hide_code: false, column: null },
        },
        {},
      ),
    ],
    [
      "Blocked · Outdated",
      derive(
        { edited: true, lastExecutionTime: 10 },
        { status: "disabled-transitively" },
      ),
    ],
    [
      "Paused · Error · Outdated",
      derive(
        {
          edited: true,
          lastExecutionTime: 10,
          config: { disabled: true, hide_code: false, column: null },
        },
        { errored: true },
      ),
    ],
    [
      "Error · Outdated",
      derive({ edited: true, lastExecutionTime: 10 }, { errored: true }),
    ],
  ])("presents combined state as %s", (label, state) => {
    expect(presentCellStatus(state).label).toBe(label);
  });
});

describe("summarizeCellStates", () => {
  it("counts orthogonal column states", () => {
    const states = [
      derive({}, { status: "running" }),
      derive({}, { status: "queued" }),
      derive({ edited: true, lastExecutionTime: 10 }),
      derive({}, { errored: true }),
      derive(
        {
          edited: true,
          lastExecutionTime: 10,
          config: { disabled: true, hide_code: false, column: null },
        },
        {},
      ),
    ];

    expect(summarizeCellStates(states)).toEqual({
      running: 1,
      queued: 1,
      pending: 1,
      unavailableOutdated: 1,
      failed: 1,
    });
  });
});
