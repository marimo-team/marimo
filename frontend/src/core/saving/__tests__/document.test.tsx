/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import { renderHook } from "@testing-library/react";
import { atom, createStore } from "jotai";
import type { PropsWithChildren } from "react";
import { describe, expect, it, vi } from "vitest";
import { DocumentWrapper } from "@/__mocks__/document";
import { partial } from "@/__mocks__/partial";
import type {
  DocumentModel,
  DocumentSyncStatus,
} from "@/core/notebook/document";
import type { NotebookReplica } from "@/core/notebook/replica";
import {
  type FakeSave,
  fakeBackend,
} from "@/core/notebook/replica/__tests__/fixtures";
import { activeNotebookReplicaAtom } from "@/core/session/active-notebook";
import { Deferred } from "@/utils/Deferred";
import { useNotebookDocumentSave } from "../document";

const confirmed: Protocol.Document = {
  notebook_id: "n1",
  order: [],
  app_config: {},
  etag: "e1",
  saved_etag: null,
  order_etag: "o1",
  app_config_etag: "a1",
  version: 1,
};

const saved: FakeSave = async () => ({
  ok: true,
  status: 200,
  data: { document: confirmed, cells: {} },
});

function setup({
  flush = vi.fn(async () => confirmed),
  save = vi.fn(saved),
  connected = true,
}: {
  flush?: DocumentModel["flush"];
  save?: FakeSave;
  connected?: boolean;
} = {}) {
  const store = createStore();
  const model = partial<DocumentModel>(
    {
      flush,
      retry: vi.fn(),
      syncStatusAtom: atom<DocumentSyncStatus>({ status: "idle" }),
    },
    "model",
  );
  if (connected) {
    store.set(
      activeNotebookReplicaAtom,
      partial<NotebookReplica>(
        { backendAtom: atom(fakeBackend({ save })) },
        "replica",
      ),
    );
  }
  const wrapper = ({ children }: PropsWithChildren) => (
    <DocumentWrapper store={store} model={model}>
      {children}
    </DocumentWrapper>
  );
  const { result } = renderHook(() => useNotebookDocumentSave(), { wrapper });
  return { saveDocument: result.current, flush, save };
}

describe("useNotebookDocumentSave", () => {
  it("flushes this client's edits, then saves the flushed notebook", async () => {
    const flushed = new Deferred<Protocol.Document>();
    const save = vi.fn(saved);
    const { saveDocument } = setup({ flush: () => flushed.promise, save });
    const saving = saveDocument();
    await Promise.resolve();
    expect(save).not.toHaveBeenCalled();
    flushed.resolve(confirmed);
    await saving;
    expect(save).toHaveBeenCalledWith("n1");
  });

  it("does not save when flushing fails", async () => {
    const save = vi.fn(saved);
    const { saveDocument } = setup({
      flush: () => Promise.reject(new Error("unsynchronized edit")),
      save,
    });
    await expect(saveDocument()).rejects.toThrow("unsynchronized edit");
    expect(save).not.toHaveBeenCalled();
  });

  it("reports the host's refusal", async () => {
    const { saveDocument } = setup({
      save: async () => ({
        ok: false,
        status: 409,
        problem: {
          type: "about:blank",
          title: "Conflict",
          status: 409,
          detail: "storage full",
        },
      }),
    });
    await expect(saveDocument()).rejects.toThrow("storage full");
  });

  it("does not save while no notebook is connected", async () => {
    const flush = vi.fn(async () => confirmed);
    const { saveDocument } = setup({ flush, connected: false });
    await expect(saveDocument()).rejects.toThrow(
      "The notebook is not connected",
    );
    expect(flush).not.toHaveBeenCalled();
  });
});
