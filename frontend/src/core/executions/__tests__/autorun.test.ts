/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import { createStore } from "jotai";
import { describe, expect, it, onTestFinished, vi } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
import {
  document,
  withCells,
} from "@/core/notebook/document/__tests__/fixtures";
import {
  fakeBackend,
  type FakeRun,
} from "@/core/notebook/replica/__tests__/fixtures";
import { activeNotebookReplicaAtom } from "@/core/session/active-notebook";
import { Deferred } from "@/utils/Deferred";
import { createNotebookAutorun } from "../autorun";

function setup({
  records = [],
  status = "running",
  operations = ["notebook.edit", "runtime.run"],
}: {
  records?: Protocol.Execution[];
  status?: Protocol.RuntimeStatus;
  operations?: Protocol.Notebook["operations"];
} = {}) {
  const store = createStore();
  const replica = MockExecutions.seed(
    store,
    records,
    MockExecutions.runtime(status),
    document(),
  );
  const notebook = { ...MockExecutions.notebook(), operations };
  store.set(replica.notebookAtom, notebook);
  const run = vi.fn<FakeRun>(async (id, request) => ({
    ok: true,
    status: 202,
    data: {
      id: "startup-run",
      notebook_id: id,
      runtime_id: "r1",
      cells: request.cells.map(({ id }) => id),
      status: "queued",
      outcome: null,
      started_at: null,
      completed_at: null,
    },
  }));
  store.set(replica.backendAtom, fakeBackend({ run }));
  const prepare = vi.fn<() => Promise<boolean>>().mockResolvedValue(true);
  const autorun = createNotebookAutorun({ store, replica, prepare });
  const onError = vi.fn();
  const start = (autoRun = true) => {
    const controller = new AbortController();
    autorun.start({ autoRun, signal: controller.signal, onError });
    onTestFinished(() => controller.abort());
    return controller;
  };
  const executions = (records: Protocol.Execution[]) => {
    store.set(
      replica.executionsAtom,
      MockExecutions.inputs(records).executions,
    );
  };
  return {
    store,
    replica,
    notebook,
    run,
    prepare,
    onError,
    start,
    executions,
    autorun,
  };
}

describe("notebook startup", () => {
  it("waits for both the ready snapshot and the running runtime", async () => {
    const { store, replica, notebook, start, run } = setup({
      status: "starting",
    });
    store.set(replica.notebookAtom, null);
    start();
    store.set(replica.runtimeAtom, MockExecutions.runtime("running"));
    await Promise.resolve();
    expect(run).not.toHaveBeenCalled();

    store.set(replica.notebookAtom, notebook);
    await vi.waitFor(() =>
      expect(run).toHaveBeenCalledExactlyOnceWith("n1", {
        cells: [{ id: "c1" }, { id: "c2" }],
        idempotencyKey: "startup:n1:r1",
      }),
    );
  });

  it.each([false, true])(
    "does not run a lazy runtime after autorun changes to %s",
    async (autoRun) => {
      const { start, run } = setup();
      start(false).abort();
      start(autoRun);
      await Promise.resolve();
      expect(run).not.toHaveBeenCalled();
    },
  );

  it.each([{ operations: [] }, { operations: ["notebook.edit"] }])(
    "does not initialize a connection with operations $operations",
    async ({ operations }) => {
      const { start, run } = setup({ operations });
      start();
      await Promise.resolve();
      expect(run).not.toHaveBeenCalled();
    },
  );

  it("can autorun without permission to edit the notebook", async () => {
    const { start, run } = setup({ operations: ["runtime.run"] });
    start();
    await vi.waitFor(() => expect(run).toHaveBeenCalledOnce());
  });

  it.each([MockExecutions.completed("c1"), MockExecutions.running("c1")])(
    "leaves an existing runtime alone, including cells never run",
    async (execution) => {
      const { start, run } = setup({ records: [execution] });
      start();
      await Promise.resolve();
      expect(run).not.toHaveBeenCalled();
    },
  );

  it("does not autorun when the host has accepted a run without executions yet", async () => {
    const { store, replica, start, run } = setup();
    store.set(replica.executionsAtom, (state) => ({
      ...state,
      runs: new Map([
        [
          "run-1",
          {
            id: "run-1",
            notebook_id: "n1",
            runtime_id: "r1",
            cells: ["c1"],
            status: "queued",
            outcome: null,
            started_at: null,
            completed_at: null,
          },
        ],
      ]),
    }));
    start();
    await Promise.resolve();
    expect(run).not.toHaveBeenCalled();
  });

  it("reads execution history from its supplied replica, not the active editor", async () => {
    const { store, start, run } = setup({
      records: [MockExecutions.completed("c1")],
    });
    store.set(activeNotebookReplicaAtom, null);
    start();
    await Promise.resolve();
    expect(run).not.toHaveBeenCalled();
  });

  it("does not repeat startup after reconnect or effect remount, but starts a replacement runtime", async () => {
    const { store, replica, notebook, start, run } = setup();
    const first = start();
    await vi.waitFor(() => expect(run).toHaveBeenCalledOnce());
    first.abort();
    start();
    store.set(replica.notebookAtom, null);
    store.set(replica.notebookAtom, notebook);
    await Promise.resolve();
    expect(run).toHaveBeenCalledOnce();

    store.set(replica.runtimeAtom, {
      ...MockExecutions.runtime("running"),
      id: "r2",
    });
    await vi.waitFor(() => expect(run).toHaveBeenCalledTimes(2));
    expect(run).toHaveBeenLastCalledWith("n1", {
      cells: [{ id: "c1" }, { id: "c2" }],
      idempotencyKey: "startup:n1:r2",
    });
  });

  it("survives an effect remount while preparation is pending", async () => {
    const { start, run, prepare } = setup();
    const sync = new Deferred<boolean>();
    prepare.mockReturnValue(sync.promise);
    start().abort();
    start();
    sync.resolve(true);
    await vi.waitFor(() => expect(run).toHaveBeenCalledOnce());
  });

  it("settles without running when preparation yields to another owner", async () => {
    const { store, start, run, prepare, autorun, executions } = setup();
    prepare.mockResolvedValue(false);
    start();
    await vi.waitFor(() => expect(store.get(autorun.pendingAtom)).toBe(false));
    executions([]);
    expect(run).not.toHaveBeenCalled();
  });

  it("reads the document after preparation and leaves disabled-cell policy to the host", async () => {
    const { store, replica, start, run, prepare } = setup();
    const sync = new Deferred<boolean>();
    prepare.mockReturnValue(sync.promise);
    start();
    const initial = document();
    const cell = initial.cells.get("c2")!;
    const next = withCells(initial, {
      c2: { ...cell, config: { ...cell.config, disabled: true } },
    });
    store.set(replica.documentAtom, next);
    sync.resolve(true);
    await vi.waitFor(() =>
      expect(run).toHaveBeenCalledExactlyOnceWith("n1", {
        cells: [{ id: "c1" }, { id: "c2" }],
        idempotencyKey: "startup:n1:r1",
      }),
    );
  });

  it("does not run cells added to a notebook that opened empty", async () => {
    const { store, replica, start, run, prepare } = setup();
    store.set(
      replica.documentAtom,
      withCells(document(), { c1: null, c2: null }),
    );
    start();
    await vi.waitFor(() => expect(prepare).toHaveResolved());
    store.set(replica.documentAtom, document());
    await Promise.resolve();
    expect(run).not.toHaveBeenCalled();
  });

  it("settles a fast run pruned before its command response arrives", async () => {
    const { store, replica, start, run, autorun } = setup();
    const response = new Deferred<Awaited<ReturnType<FakeRun>>>();
    run.mockReturnValue(response.promise);
    start();
    await vi.waitFor(() => expect(run).toHaveBeenCalledOnce());
    const record: Protocol.Run = {
      id: "fast",
      notebook_id: "n1",
      runtime_id: "r1",
      cells: ["c1", "c2"],
      status: "completed",
      outcome: "succeeded",
      started_at: null,
      completed_at: null,
    };
    store.set(replica.executionsAtom, (state) => ({
      ...state,
      runs: new Map([[record.id, record]]),
    }));
    store.set(replica.executionsAtom, (state) => ({
      ...state,
      runs: new Map(),
    }));
    expect(store.get(autorun.pendingAtom)).toBe(true);
    response.resolve({ ok: true, status: 202, data: record });
    await vi.waitFor(() => expect(store.get(autorun.pendingAtom)).toBe(false));
    expect(run).toHaveBeenCalledOnce();
  });

  it("settles quietly when the host refuses this connection the run", async () => {
    // A second tab on the same notebook is a viewer. The host advertises
    // the same operations to it and refuses the call.
    const { store, start, run, autorun, onError } = setup();
    run.mockResolvedValue({
      ok: false,
      status: 403,
      problem: {
        type: "urn:marimo:problem:forbidden",
        title: "Forbidden",
        status: 403,
      },
    });
    start();
    await vi.waitFor(() => expect(store.get(autorun.pendingAtom)).toBe(false));
    expect(run).toHaveBeenCalledOnce();
    expect(onError).not.toHaveBeenCalled();
  });

  it("settles when a retried request returns a run that already ended", async () => {
    const { store, start, run, autorun } = setup();
    run.mockImplementation(async (id, request) => ({
      ok: true,
      status: 202,
      data: {
        id: "earlier-startup-run",
        notebook_id: id,
        runtime_id: "r1",
        cells: request.cells.map((cell) => cell.id),
        status: "completed",
        outcome: "succeeded",
        started_at: null,
        completed_at: null,
      },
    }));
    start();
    await vi.waitFor(() => expect(store.get(autorun.pendingAtom)).toBe(false));
    expect(run).toHaveBeenCalledOnce();
  });

  it("reports a failed submission once instead of looping on stream updates", async () => {
    const { start, run, onError, executions } = setup();
    run.mockRejectedValue(new Error("offline"));
    start();
    await vi.waitFor(() => expect(onError).toHaveBeenCalledOnce());
    executions([]);
    await Promise.resolve();
    expect(run).toHaveBeenCalledOnce();
    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({ message: "Failed to autorun notebook" }),
    );
  });

  it("does not submit after the session ends during preparation", async () => {
    const { start, run, prepare, onError } = setup();
    const sync = new Deferred<boolean>();
    prepare.mockReturnValue(sync.promise);
    start().abort();
    sync.resolve(true);
    await Promise.resolve();
    expect(run).not.toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
  });

  it.each(["resolved", "rejected"])(
    "discards a %s preparation when its runtime is replaced",
    async (outcome) => {
      const { store, replica, start, run, prepare, onError } = setup();
      const sync = new Deferred<boolean>();
      prepare.mockReturnValueOnce(sync.promise);
      start();
      store.set(replica.runtimeAtom, {
        ...MockExecutions.runtime("running"),
        id: "r2",
      });
      if (outcome === "resolved") {
        sync.resolve(true);
      } else {
        sync.reject(new Error("Previous runtime disconnected"));
      }
      await vi.waitFor(() =>
        expect(run).toHaveBeenCalledExactlyOnceWith("n1", {
          cells: [{ id: "c1" }, { id: "c2" }],
          idempotencyKey: "startup:n1:r2",
        }),
      );
      expect(onError).not.toHaveBeenCalled();
    },
  );
});
