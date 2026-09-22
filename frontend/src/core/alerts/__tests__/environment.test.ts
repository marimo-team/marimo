/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { NotificationMessageData } from "@/core/kernel/messages";
import { emptyEnvironmentState, reduceEnvironmentState } from "../environment";

function progress(
  operation_id: string,
  update: Partial<NotificationMessageData<"environment-operation">> = {},
): NotificationMessageData<"environment-operation"> {
  return {
    operation_id,
    action: "install",
    source: "kernel",
    status: { kind: "running" },
    packages: { numpy: "running" },
    logs: { numpy: "Downloading\n" },
    log_mode: "append",
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
        packages: { numpy: "succeeded" },
        logs: { numpy: "Installed\n" },
        log_mode: "append",
      }),
    );
    expect(result).toEqual({
      restart_required: false,
      operations: [
        {
          operation_id: "one",
          action: "install",
          source: "kernel",
          status: { kind: "succeeded" },
          packages: { numpy: "succeeded" },
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
        logs: {},
      }),
    );
    expect(state.operations.map((op) => [op.operation_id, op.logs])).toEqual([
      ["one", { numpy: "Downloading\n" }],
      ["two", { numpy: "Other\n" }],
    ]);
    state = reduceEnvironmentState(state, progress("retry", { logs: {} }));
    expect(state.operations.map((op) => [op.operation_id, op.logs])).toEqual([
      ["two", { numpy: "Other\n" }],
      ["retry", {}],
    ]);
  });

  it("replaces named logs independently of the package map", () => {
    const state = reduceEnvironmentState(
      emptyEnvironmentState(),
      progress("one", {
        packages: { numpy: "succeeded", pandas: "running" },
        logs: { numpy: "Old\n", pandas: "Old\n" },
      }),
    );
    const result = reduceEnvironmentState(
      state,
      progress("one", {
        log_mode: "replace",
        logs: { numpy: "", pandas: "Ignored\n" },
      }),
    );
    expect(result.operations[0].logs).toEqual({
      numpy: "",
      pandas: "Ignored\n",
    });
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
        packages: { numpy: "succeeded" },
        logs: {},
      }),
    );
    expect(state).toEqual({
      restart_required: true,
      operations: [
        {
          operation_id: "two",
          action: "install",
          source: "kernel",
          status: { kind: "succeeded" },
          packages: { numpy: "succeeded" },
          logs: {},
        },
      ],
    });
  });
});
