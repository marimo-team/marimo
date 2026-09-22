/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { NotificationMessageData } from "@/core/kernel/messages";
import { emptyEnvironmentState, reduceEnvironmentState } from "../environment";

function progress(
  operation_id: string,
  update: Partial<NotificationMessageData<"installing-package-alert">> = {},
): NotificationMessageData<"installing-package-alert"> {
  return {
    operation_id,
    source: "kernel",
    status: { kind: "running" },
    packages: { numpy: "installing" },
    logs: { numpy: "Downloading\n" },
    log_status: "append",
    ...update,
  };
}

describe("environment progress", () => {
  it("continues snapshot logs without mutating or duplicating them", () => {
    const snapshot = reduceEnvironmentState(
      emptyEnvironmentState(),
      progress("one"),
    );
    const result = reduceEnvironmentState(
      snapshot,
      progress("one", {
        status: { kind: "succeeded" },
        packages: { numpy: "installed" },
        logs: { numpy: "Installed\n" },
        log_status: "done",
      }),
    );
    expect(result).toEqual({
      restart_required: false,
      operations: [
        {
          operation_id: "one",
          source: "kernel",
          status: { kind: "succeeded" },
          packages: { numpy: "installed" },
          logs: { numpy: "Downloading\nInstalled\n" },
        },
      ],
    });
    expect(snapshot.operations[0].logs).toEqual({ numpy: "Downloading\n" });
  });

  it("isolates overlapping operations and starts retries with fresh logs", () => {
    let state = reduceEnvironmentState(
      emptyEnvironmentState(),
      progress("one"),
    );
    state = reduceEnvironmentState(
      state,
      progress("two", { logs: { numpy: "Other\n" } }),
    );
    state = reduceEnvironmentState(
      state,
      progress("one", {
        status: { kind: "failed", error: "Network unavailable" },
        logs: null,
      }),
    );
    expect(state.operations.map((op) => [op.operation_id, op.logs])).toEqual([
      ["one", { numpy: "Downloading\n" }],
      ["two", { numpy: "Other\n" }],
    ]);
    state = reduceEnvironmentState(state, progress("retry", { logs: null }));
    expect(state.operations.map((op) => [op.operation_id, op.logs])).toEqual([
      ["two", { numpy: "Other\n" }],
      ["retry", {}],
    ]);
  });

  it("replaces a package log on start and removes omitted packages", () => {
    const state = reduceEnvironmentState(
      emptyEnvironmentState(),
      progress("one", {
        packages: { numpy: "installed", pandas: "installing" },
        logs: { numpy: "Old\n", pandas: "Old\n" },
      }),
    );
    const result = reduceEnvironmentState(
      state,
      progress("one", {
        log_status: "start",
        logs: { numpy: "", pandas: "Ignored\n" },
      }),
    );
    expect(result.operations[0].logs).toEqual({ numpy: "" });
  });

  it("keeps a restart requirement after a later operation succeeds", () => {
    let state = reduceEnvironmentState(
      emptyEnvironmentState(),
      progress("one", {
        status: { kind: "restart-required", reason: "Python changed" },
      }),
    );
    state = reduceEnvironmentState(
      state,
      progress("two", {
        status: { kind: "succeeded" },
        packages: { numpy: "installed" },
        logs: null,
      }),
    );
    expect(state).toEqual({
      restart_required: true,
      operations: [
        {
          operation_id: "two",
          source: "kernel",
          status: { kind: "succeeded" },
          packages: { numpy: "installed" },
          logs: {},
        },
      ],
    });
  });
});
