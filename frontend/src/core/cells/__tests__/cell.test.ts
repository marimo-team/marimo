/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import type { CellExecutionView, CellFreshness } from "@/core/executions";
import { consoleOutputIsStale, outputIsLoading, outputIsStale } from "../cell";

const CURRENT: CellFreshness = { sourceChanged: false, inputsChanged: false };
const EDITED: CellFreshness = { sourceChanged: true, inputsChanged: false };
const REPLACED: CellFreshness = { sourceChanged: false, inputsChanged: true };
const BOTH: CellFreshness = { sourceChanged: true, inputsChanged: true };

type View = Pick<CellExecutionView, "status" | "outcome" | "startedAt">;

function view(overrides: Partial<View>): View {
  return {
    status: "idle",
    outcome: null,
    startedAt: null,
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
  it.each(["queued", "running"] as const)(
    "keeps previous output visible while %s",
    (status) => {
      expect(outputIsStale(view({ status }), BOTH, true)).toBe(false);
    },
  );

  it("should return true if the cell has stale inputs", () => {
    expect(outputIsStale(view({}), REPLACED, false)).toBe(true);
  });

  it("should return false if the cell is interrupted", () => {
    expect(outputIsStale(view({ outcome: "cancelled" }), CURRENT, false)).toBe(
      false,
    );
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

  it("should return true if the cell is interrupted and edited since", () => {
    expect(outputIsStale(view({ outcome: "cancelled" }), EDITED, true)).toBe(
      true,
    );
  });

  it("should still dim for changed inputs in a read view when the source also changed", () => {
    expect(outputIsStale(view({}), BOTH, false)).toBe(true);
  });
});

describe("consoleOutputIsStale", () => {
  it("keeps the queued console visible", () => {
    expect(consoleOutputIsStale(view({ status: "queued" }), CURRENT)).toBe(
      false,
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
    expect(consoleOutputIsStale(view({ outcome: "cancelled" }), EDITED)).toBe(
      false,
    );
  });

  it("should return false if the cell is interrupted but has stale inputs", () => {
    expect(outputIsStale(view({ outcome: "cancelled" }), REPLACED, false)).toBe(
      false,
    );
  });
});
