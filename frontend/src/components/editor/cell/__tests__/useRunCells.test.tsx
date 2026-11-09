/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import { act, renderHook } from "@testing-library/react";
import { atom, Provider } from "jotai";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import { notebookAtom } from "@/core/cells/cells";
import type { DocumentModel } from "@/core/notebook/document";
import {
  cell,
  document as documentOf,
  withCells,
} from "@/core/notebook/document/__tests__/fixtures";
import {
  type FakeRun,
  fakeBackend,
} from "@/core/notebook/replica/__tests__/fixtures";
import { activeDocumentModelAtom } from "@/core/session/active-notebook";
import { store } from "@/core/state/jotai";
import { useRunStaleCells } from "../useRunCells";

const toast = vi.fn();
vi.mock("@/components/ui/use-toast", () => ({
  toast: (...args: unknown[]) => toast(...args),
}));
vi.mock("@/core/runtime/config", () => ({
  startRuntimeIfLazy: async () => undefined,
}));

const C1 = cellId("c1");
const C2 = cellId("c2");

const wrapper = ({ children }: { children: ReactNode }) => (
  <Provider store={store}>{children}</Provider>
);

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

describe("useRunStaleCells", () => {
  let run: ReturnType<typeof vi.fn<FakeRun>>;

  beforeEach(() => {
    toast.mockClear();
    run = vi.fn<FakeRun>(async (_notebookId, request) => ({
      ok: true,
      status: 202,
      data: accepted(request.cells?.map((cell) => cell.id) ?? []),
    }));
  });

  afterEach(() => {
    store.set(activeDocumentModelAtom, null);
  });

  function seed(records: Protocol.Execution[]) {
    const document = documentOf();
    const replica = MockExecutions.seed(
      store,
      records,
      MockExecutions.runtime("running"),
      document,
    );
    store.set(replica.backendAtom, fakeBackend({ run }));
    return { replica, document };
  }

  function model(sync: () => Promise<Protocol.Document>) {
    store.set(activeDocumentModelAtom, {
      retry: sync,
      documentAtom: atom(null),
    } as unknown as DocumentModel);
  }

  it("syncs pending edits before choosing the stale cells", async () => {
    const { replica, document } = seed([
      MockExecutions.completed(C1, { code_fingerprint: "c1-hash" }),
      MockExecutions.completed(C2, { code_fingerprint: "c2-hash" }),
    ]);
    store.set(
      notebookAtom,
      MockNotebook.notebookState({
        cellData: { [C1]: { code: "x = 2" }, [C2]: { code: "y = 2" } },
      }),
    );
    // The edit to c1 is still in flight: the host confirms it on sync.
    const sync = vi.fn(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
      const confirmed = withCells(document, {
        [C1]: cell(C1, "x = 2", { code_fingerprint: "c1-hash-2" }),
      });
      store.set(replica.documentAtom, confirmed);
      return confirmed.revision;
    });
    model(sync);
    const { result } = renderHook(useRunStaleCells, { wrapper });

    await act(() => result.current());

    expect(sync).toHaveBeenCalled();
    expect(run).toHaveBeenCalledWith("n1", { cells: [{ id: C1 }] });
  });

  it("does nothing when the notebook changed while the flush was pending", async () => {
    seed([MockExecutions.completed(C1, { code_fingerprint: "stale" })]);
    store.set(
      notebookAtom,
      MockNotebook.notebookState({ cellData: { [C1]: { code: "x = 1" } } }),
    );
    model(async () => {
      store.set(activeDocumentModelAtom, null);
      throw new Error("aborted");
    });
    const { result } = renderHook(useRunStaleCells, { wrapper });

    await act(() => result.current());

    expect(run).not.toHaveBeenCalled();
    expect(toast).not.toHaveBeenCalled();
  });

  it("runs nothing while edits cannot reach the host", async () => {
    seed([MockExecutions.completed(C1, { code_fingerprint: "stale" })]);
    store.set(
      notebookAtom,
      MockNotebook.notebookState({ cellData: { [C1]: { code: "x = 1" } } }),
    );
    model(async () => {
      throw new Error("offline");
    });
    const { result } = renderHook(useRunStaleCells, { wrapper });

    await act(() => result.current());

    expect(run).not.toHaveBeenCalled();
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Edits not yet synced" }),
    );
  });
});
