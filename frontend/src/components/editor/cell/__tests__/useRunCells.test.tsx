/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { Provider } from "jotai";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
import { MockNotebook } from "@/__mocks__/notebook";
import { MockRequestClient } from "@/__mocks__/requests";
import { cellId } from "@/__tests__/branded";
import { notebookAtom } from "@/core/cells/cells";
import {
  cellExecutionInputsAtom,
  cellExecutionView,
  notebookQueuedOrRunningCountAtom,
} from "@/core/executions";
import { requestClientAtom } from "@/core/network/requests";
import type { DocumentModel } from "@/core/notebook/document";
import {
  cell,
  document as documentOf,
  withCells,
} from "@/core/notebook/document/__tests__/fixtures";
import { activeDocumentModelAtom } from "@/core/session/active-notebook";
import { store } from "@/core/state/jotai";
import { runCells, useRunStaleCells } from "../useRunCells";

const ENABLED = cellId("enabled");
const DISABLED = cellId("disabled");

describe("runCells", () => {
  it("sends a disabled cell to the kernel without reading it as queued", async () => {
    MockExecutions.seed(store, []);
    const notebook = MockNotebook.notebookState({
      cellData: {
        [ENABLED]: { code: "x = 1" },
        [DISABLED]: { code: "y = 2", config: { disabled: true } },
      },
    });
    const sendRun = vi.fn(async () => null);

    await runCells({
      cellIds: [ENABLED, DISABLED],
      sendRun,
      prepareForRun: vi.fn(),
      notebook,
    });

    expect(sendRun).toHaveBeenCalledWith({
      cellIds: [ENABLED, DISABLED],
      codes: ["x = 1", "y = 2"],
    });
    const inputs = store.get(cellExecutionInputsAtom);
    expect(cellExecutionView(inputs, ENABLED).status).toBe("queued");
    expect(cellExecutionView(inputs, DISABLED).status).toBe("idle");
    expect(store.get(notebookQueuedOrRunningCountAtom)).toBe(1);
  });
});

describe("useRunStaleCells", () => {
  const C1 = cellId("c1");
  const C2 = cellId("c2");

  afterEach(() => {
    store.set(activeDocumentModelAtom, null);
  });

  it("flushes pending edits before choosing the stale cells", async () => {
    const document = documentOf();
    const replica = MockExecutions.seed(
      store,
      [
        MockExecutions.completed(C1, { code_fingerprint: "c1-hash" }),
        MockExecutions.completed(C2, { code_fingerprint: "c2-hash" }),
      ],
      null,
      document,
    );
    store.set(
      notebookAtom,
      MockNotebook.notebookState({
        cellData: { [C1]: { code: "x = 2" }, [C2]: { code: "y = 2" } },
      }),
    );
    const client = MockRequestClient.create();
    store.set(requestClientAtom, client);
    // The edit to c1 is still in flight: the host confirms it on flush.
    const flush = vi.fn(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
      store.set(
        replica.documentAtom,
        withCells(document, {
          [C1]: cell(C1, "x = 2", { code_fingerprint: "c1-hash-2" }),
        }),
      );
    });
    store.set(activeDocumentModelAtom, { flush } as unknown as DocumentModel);
    const wrapper = ({ children }: { children: ReactNode }) => (
      <Provider store={store}>{children}</Provider>
    );
    const { result } = renderHook(useRunStaleCells, { wrapper });

    await act(() => result.current());

    expect(flush).toHaveBeenCalledOnce();
    expect(client.sendRun).toHaveBeenCalledWith({
      cellIds: [C1],
      codes: ["x = 2"],
    });
  });

  it("does nothing when the notebook changed while the flush was pending", async () => {
    MockExecutions.seed(
      store,
      [MockExecutions.completed(C1, { code_fingerprint: "stale" })],
      null,
      documentOf(),
    );
    store.set(
      notebookAtom,
      MockNotebook.notebookState({ cellData: { [C1]: { code: "x = 1" } } }),
    );
    const client = MockRequestClient.create();
    store.set(requestClientAtom, client);
    const flush = vi.fn(async () => {
      store.set(activeDocumentModelAtom, null);
      throw new Error("aborted");
    });
    store.set(activeDocumentModelAtom, { flush } as unknown as DocumentModel);
    const wrapper = ({ children }: { children: ReactNode }) => (
      <Provider store={store}>{children}</Provider>
    );
    const { result } = renderHook(useRunStaleCells, { wrapper });

    await act(() => result.current());

    expect(client.sendRun).not.toHaveBeenCalled();
  });

  it("still runs what is stale when the flush fails", async () => {
    MockExecutions.seed(
      store,
      [MockExecutions.completed(C1, { code_fingerprint: "stale" })],
      null,
      documentOf(),
    );
    store.set(
      notebookAtom,
      MockNotebook.notebookState({ cellData: { [C1]: { code: "x = 1" } } }),
    );
    const client = MockRequestClient.create();
    store.set(requestClientAtom, client);
    const flush = vi.fn(async () => {
      throw new Error("offline");
    });
    store.set(activeDocumentModelAtom, { flush } as unknown as DocumentModel);
    const wrapper = ({ children }: { children: ReactNode }) => (
      <Provider store={store}>{children}</Provider>
    );
    const { result } = renderHook(useRunStaleCells, { wrapper });

    await act(() => result.current());

    expect(client.sendRun).toHaveBeenCalledWith({
      cellIds: [C1],
      codes: ["x = 1"],
    });
  });
});
