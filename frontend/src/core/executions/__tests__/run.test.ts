/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import { atom } from "jotai";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
import { cellId } from "@/__tests__/branded";
import type { DocumentModel, EditableDocument } from "@/core/notebook/document";
import {
  cell,
  CONFIG,
  document as documentOf,
  withCells,
} from "@/core/notebook/document/__tests__/fixtures";
import {
  ConnectionClosedReason,
  ConnectionState,
} from "@/core/notebook/replica";
import {
  type FakeRun,
  fakeBackend,
} from "@/core/notebook/replica/__tests__/fixtures";
import { activeDocumentModelAtom } from "@/core/session/active-notebook";
import { store } from "@/core/state/jotai";
import { cellExecutionInputsAtom } from "../atoms";
import { runCells } from "../run";
import { cellExecutionView } from "../select";

const toast = vi.fn();
vi.mock("@/components/ui/use-toast", () => ({
  toast: (...args: unknown[]) => toast(...args),
}));
vi.mock("@/core/runtime/config", () => ({
  startRuntimeIfLazy: async () => undefined,
}));

const C1 = cellId("c1");
const C2 = cellId("c2");

function accepted(cells: Protocol.CellId[]): Protocol.Run {
  return {
    id: "run-1",
    notebook_id: "n1",
    runtime_id: "r1",
    cells,
    status: "queued",
    outcome: null,
    started_at: null,
    completed_at: null,
  };
}

function editable(disabled: Protocol.CellId[] = []): EditableDocument {
  const confirmed = documentOf();
  return {
    order: confirmed.revision.order,
    cells: new Map(
      [...confirmed.cells.values()].map((cell) => [
        cell.id,
        {
          ...cell,
          config: { ...cell.config, disabled: disabled.includes(cell.id) },
        },
      ]),
    ),
  };
}

/** A model whose edits sync with `sync`, confirming the fixture document by default. */
function model(
  sync: () => Promise<Protocol.Document> = async () => documentOf().revision,
  document: EditableDocument | null = editable(),
): DocumentModel {
  const model = {
    retry: vi.fn(sync),
    documentAtom: atom(document),
  } as unknown as DocumentModel;
  store.set(activeDocumentModelAtom, model);
  return model;
}

function status(id: Protocol.CellId) {
  return cellExecutionView(store.get(cellExecutionInputsAtom), id).status;
}

describe("runCells", () => {
  let run: ReturnType<typeof vi.fn<FakeRun>>;

  beforeEach(() => {
    toast.mockClear();
    run = vi.fn<FakeRun>(async (_notebookId, request) => ({
      ok: true,
      status: 202,
      data: accepted(request.cells?.map((cell) => cell.id) ?? []),
    }));
    const replica = MockExecutions.seed(
      store,
      [],
      MockExecutions.runtime("running"),
      documentOf(),
    );
    store.set(replica.backendAtom, fakeBackend({ run }));
  });

  afterEach(() => {
    store.set(activeDocumentModelAtom, null);
  });

  it("queues the cells at once, then runs them by id after the edits sync", async () => {
    const { retry } = model();

    const pending = runCells(store, [C1, C2]);
    expect(status(C1)).toBe("queued");
    expect(status(C2)).toBe("queued");
    await pending;

    // Retrying covers a synchronization that stalled before the run.
    expect(retry).toHaveBeenCalledOnce();
    expect(run).toHaveBeenCalledWith("n1", {
      cells: [{ id: C1 }, { id: C2 }],
    });
    expect(vi.mocked(retry).mock.invocationCallOrder[0]).toBeLessThan(
      run.mock.invocationCallOrder[0],
    );
    // Queued until the host plans the run or ends it.
    expect(status(C1)).toBe("queued");
    expect(toast).not.toHaveBeenCalled();
  });

  it("sends a disabled cell without reading it as queued", async () => {
    const replica = MockExecutions.seed(
      store,
      [],
      MockExecutions.runtime("running"),
      withCells(documentOf(), {
        c2: cell("c2", "y = 2", { config: { ...CONFIG, disabled: true } }),
      }),
    );
    store.set(replica.backendAtom, fakeBackend({ run }));
    model(undefined, editable([C2]));

    await runCells(store, [C1, C2]);

    expect(run).toHaveBeenCalledWith("n1", {
      cells: [{ id: C1 }, { id: C2 }],
    });
    expect(status(C1)).toBe("queued");
    expect(status(C2)).toBe("idle");
  });

  it("waits for the runtime to run before submitting", async () => {
    const replica = MockExecutions.seed(
      store,
      [],
      MockExecutions.runtime("starting"),
      documentOf(),
    );
    store.set(replica.backendAtom, fakeBackend({ run }));
    model();

    const pending = runCells(store, [C1]);
    await Promise.resolve();
    expect(status(C1)).toBe("queued");
    expect(run).not.toHaveBeenCalled();

    store.set(replica.runtimeAtom, MockExecutions.runtime("running"));
    await pending;
    expect(run).toHaveBeenCalledOnce();
  });

  it("records the request once the stream has a notebook, as after a reconnect", async () => {
    const replica = MockExecutions.seed(store, [], null, documentOf());
    store.set(replica.backendAtom, fakeBackend({ run }));
    store.set(replica.notebookAtom, null);
    model();

    const pending = runCells(store, [C1]);
    await Promise.resolve();
    expect(run).not.toHaveBeenCalled();

    // The real replica reports both at once, from one snapshot.
    store.set(replica.runtimeAtom, MockExecutions.runtime("running"));
    store.set(replica.notebookAtom, MockExecutions.notebook());
    await pending;

    expect(run).toHaveBeenCalledWith("n1", { cells: [{ id: C1 }] });
    expect(status(C1)).toBe("queued");
    expect(toast).not.toHaveBeenCalled();
  });

  it("withdraws the submission and reports when the edits cannot sync", async () => {
    model(async () => {
      throw new Error("offline");
    });

    await runCells(store, [C1]);

    expect(run).not.toHaveBeenCalled();
    expect(status(C1)).toBe("idle");
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Failed to run", variant: "danger" }),
    );
  });

  it("withdraws the submission and reports when the runtime has failed", async () => {
    const replica = MockExecutions.seed(
      store,
      [],
      { ...MockExecutions.runtime("failed"), message: "The kernel exited" },
      documentOf(),
    );
    store.set(replica.backendAtom, fakeBackend({ run }));
    model();

    await runCells(store, [C1]);

    expect(run).not.toHaveBeenCalled();
    expect(status(C1)).toBe("idle");
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({ description: "The kernel exited" }),
    );
  });

  it("withdraws the submission and reports when the notebook has no runtime", async () => {
    const replica = MockExecutions.seed(store, [], null, documentOf());
    store.set(replica.backendAtom, fakeBackend({ run }));
    model();

    await runCells(store, [C1]);

    expect(run).not.toHaveBeenCalled();
    expect(status(C1)).toBe("idle");
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({ description: "The notebook has no runtime" }),
    );
  });

  it("stops waiting for the runtime once the connection closes", async () => {
    const replica = MockExecutions.seed(
      store,
      [],
      MockExecutions.runtime("starting"),
      documentOf(),
    );
    store.set(replica.backendAtom, fakeBackend({ run }));
    model();

    const pending = runCells(store, [C1]);
    await Promise.resolve();
    expect(status(C1)).toBe("queued");

    store.set(replica.connectionAtom, {
      state: ConnectionState.CLOSED,
      code: ConnectionClosedReason.KERNEL_DISCONNECTED,
      reason: "kernel not found",
    });
    await pending;

    expect(run).not.toHaveBeenCalled();
    expect(status(C1)).toBe("idle");
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({ description: "The notebook is disconnected" }),
    );
  });

  it("withdraws the submission and reports when the host refuses the run", async () => {
    run.mockResolvedValue({
      ok: false,
      status: 409,
      problem: {
        type: "tag:marimo.io,2026:host/conflict",
        title: "Conflict",
        status: 409,
        detail: "the runtime is starting.",
      },
    });
    model();

    await runCells(store, [C1]);

    expect(status(C1)).toBe("idle");
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({ description: "the runtime is starting." }),
    );
  });

  it("withdraws quietly when the connection is read-only", async () => {
    run.mockResolvedValue({
      ok: false,
      status: 403,
      problem: {
        type: "tag:marimo.io,2026:host/forbidden",
        title: "Forbidden",
        status: 403,
      },
    });
    model();

    await runCells(store, [C1]);

    expect(status(C1)).toBe("idle");
    expect(toast).not.toHaveBeenCalled();
  });

  it("does not run when the notebook closed while the edits synced", async () => {
    model(async () => {
      store.set(activeDocumentModelAtom, null);
      return documentOf().revision;
    });

    await runCells(store, [C1]);

    expect(run).not.toHaveBeenCalled();
    expect(toast).not.toHaveBeenCalled();
  });

  it("does not run in a notebook that replaced the one the request was made in", async () => {
    // Islands keep the replica and model while the worker's session changes.
    const replica = MockExecutions.seed(
      store,
      [],
      MockExecutions.runtime("running"),
      documentOf(),
    );
    store.set(replica.backendAtom, fakeBackend({ run }));
    model(async () => {
      store.set(replica.notebookAtom, MockExecutions.notebook("n2"));
      return documentOf("n2").revision;
    });

    const pending = runCells(store, [C1]);
    expect(status(C1)).toBe("queued");
    await pending;

    expect(run).not.toHaveBeenCalled();
    expect(status(C1)).toBe("idle");
    expect(toast).not.toHaveBeenCalled();
  });

  it("leaves the replacing notebook's request when a late refusal lands", async () => {
    const replica = MockExecutions.seed(
      store,
      [],
      MockExecutions.runtime("running"),
      documentOf(),
    );
    store.set(replica.backendAtom, fakeBackend({ run }));
    model(
      async () =>
        documentOf(store.get(replica.notebookAtom)?.id ?? "n1").revision,
    );
    let refuse = (): void => undefined;
    run.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          refuse = () =>
            resolve({
              ok: false,
              status: 409,
              problem: {
                type: "tag:marimo.io,2026:host/conflict",
                title: "Conflict",
                status: 409,
              },
            });
        }),
    );

    const first = runCells(store, [C1]);
    await vi.waitFor(() => expect(run).toHaveBeenCalledOnce());
    store.set(replica.notebookAtom, MockExecutions.notebook("n2"));
    const second = runCells(store, [C1]);
    await vi.waitFor(() => expect(run).toHaveBeenCalledTimes(2));
    expect(status(C1)).toBe("queued");

    refuse();
    await first;
    await second;

    expect(run).toHaveBeenLastCalledWith("n2", { cells: [{ id: C1 }] });
    expect(status(C1)).toBe("queued");
  });

  it("does nothing without an open notebook", async () => {
    await runCells(store, [C1]);

    expect(run).not.toHaveBeenCalled();
    expect(status(C1)).toBe("idle");
  });
});
