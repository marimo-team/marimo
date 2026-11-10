/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import { createStore } from "jotai";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
import {
  fakeBackend,
  type FakeInterrupt,
} from "@/core/notebook/replica/__tests__/fixtures";
import { activeNotebookReplicaAtom } from "@/core/session/active-notebook";
import { interruptRuntime } from "../interrupt";

const toast = vi.fn();
vi.mock("@/components/ui/use-toast", () => ({
  toast: (...args: unknown[]) => toast(...args),
}));

function run(
  id: string,
  status: Protocol.Lifecycle = "running",
  runtimeId = "r1",
): Protocol.Run {
  return {
    id,
    notebook_id: "n1",
    runtime_id: runtimeId,
    cells: [],
    status,
    outcome: status === "completed" ? "succeeded" : null,
    started_at: status === "queued" ? null : MockExecutions.T0,
    completed_at: status === "completed" ? MockExecutions.T1 : null,
  };
}

function setup(runs: Protocol.Run[]) {
  const store = createStore();
  const replica = MockExecutions.seed(
    store,
    [],
    MockExecutions.runtime("running"),
  );
  const interrupt = vi.fn<FakeInterrupt>(async () => ({
    ok: true,
    status: 202,
    data: MockExecutions.runtime("running"),
  }));
  store.set(replica.backendAtom, fakeBackend({ interrupt }));
  store.set(replica.executionsAtom, {
    runs: new Map(runs.map((run) => [run.id, run])),
    executions: new Map(),
    latest: new Map(),
  });
  return { store, replica, interrupt };
}

describe("interruptRuntime", () => {
  beforeEach(() => toast.mockClear());

  it.each([
    { runs: [] },
    { runs: [run("queued", "queued")] },
    { runs: [run("browser"), run("code-mode"), run("queued", "queued")] },
  ])(
    "interrupts the runtime once regardless of recorded runs: %j",
    async ({ runs }) => {
      const { store, replica, interrupt } = setup(runs);

      await interruptRuntime(store);

      expect(interrupt.mock.calls).toEqual([["n1"]]);
      // The stream, not the acknowledgement, determines the work's outcome.
      expect([...store.get(replica.executionsAtom).runs.values()]).toEqual(
        runs,
      );
      expect(toast).not.toHaveBeenCalled();
    },
  );

  it.each([404, 409])(
    "tolerates a runtime that stopped before the request: %s",
    async (status) => {
      const { store, interrupt } = setup([]);
      interrupt.mockResolvedValue({
        ok: false,
        status,
        problem: {
          type: `tag:marimo.io,2026:host/${status === 404 ? "no-runtime" : "conflict"}`,
          title: "The runtime has stopped",
          status,
        },
      });

      await interruptRuntime(store);

      expect(interrupt.mock.calls).toEqual([["n1"]]);
      expect(toast).not.toHaveBeenCalled();
    },
  );

  it("sends the request even when the local runtime record is absent", async () => {
    const { store, replica, interrupt } = setup([]);
    store.set(replica.runtimeAtom, null);

    await interruptRuntime(store);

    expect(interrupt.mock.calls).toEqual([["n1"]]);
  });

  it("does nothing without a connected notebook", async () => {
    const { store, replica, interrupt } = setup([]);
    store.set(replica.backendAtom, null);
    await interruptRuntime(store);
    store.set(activeNotebookReplicaAtom, null);
    await interruptRuntime(store);

    expect(interrupt).not.toHaveBeenCalled();
    expect(toast).not.toHaveBeenCalled();
  });

  it.each([
    { status: 403, toasts: [] },
    {
      status: 500,
      toasts: [
        [
          {
            title: "Failed to interrupt",
            description: "Interrupt refused",
            variant: "danger",
          },
        ],
      ],
    },
  ])(
    "handles a host refusal with status $status",
    async ({ status, toasts }) => {
      const { store, interrupt } = setup([run("running")]);
      interrupt.mockResolvedValue({
        ok: false,
        status,
        problem: {
          type: `tag:marimo.io,2026:host/${status === 403 ? "forbidden" : "internal"}`,
          title: "Interrupt refused",
          status,
        },
      });

      await interruptRuntime(store);

      expect(toast.mock.calls).toEqual(toasts);
    },
  );

  it("reports transport failures without leaving an unhandled rejection", async () => {
    const { store, interrupt } = setup([run("running")]);
    interrupt.mockRejectedValue(new Error("Disconnected"));

    await interruptRuntime(store);

    expect(toast).toHaveBeenCalledExactlyOnceWith({
      title: "Failed to interrupt",
      description: "Disconnected",
      variant: "danger",
    });
  });
});
