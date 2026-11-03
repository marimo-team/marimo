/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import { atom, createStore } from "jotai";
import { describe, expect, it } from "vitest";
import { partial } from "@/__mocks__/partial";
import type {
  DocumentModel,
  DocumentSyncStatus,
} from "@/core/notebook/document";
import type { Document, NotebookReplica } from "@/core/notebook/replica";
import {
  activeDocumentModelAtom,
  activeNotebookReplicaAtom,
} from "@/core/session/active-notebook";
import { initialLayoutState, layoutStateAtom } from "../../layout/state";
import { documentVersionAtom, needsSaveAtom, savedLayoutAtom } from "../state";

function revision(
  overrides: Partial<Protocol.Document> = {},
): Protocol.Document {
  return {
    notebook_id: "nb",
    order: [],
    app_config: {},
    etag: "v2",
    saved_etag: "v2",
    order_etag: "order",
    app_config_etag: "config",
    version: 2,
    ...overrides,
  };
}

function connect(
  store: ReturnType<typeof createStore>,
  document: Document | null,
  status: DocumentSyncStatus["status"] = "idle",
) {
  store.set(
    activeNotebookReplicaAtom,
    partial<NotebookReplica>({ documentAtom: atom(document) }, "replica"),
  );
  store.set(
    activeDocumentModelAtom,
    partial<DocumentModel>(
      { syncStatusAtom: atom({ status } as DocumentSyncStatus) },
      "model",
    ),
  );
}

describe("needsSaveAtom", () => {
  it("is false without a connected document", () => {
    const store = createStore();
    expect(store.get(needsSaveAtom)).toBe(false);
    expect(store.get(documentVersionAtom)).toBeNull();
    connect(store, null);
    expect(store.get(needsSaveAtom)).toBe(false);
  });

  it("compares the host's etag with what it last wrote", () => {
    const store = createStore();
    connect(store, { revision: revision(), cells: new Map() });
    expect(store.get(needsSaveAtom)).toBe(false);
    expect(store.get(documentVersionAtom)).toBe(2);
    connect(store, { revision: revision({ etag: "v3" }), cells: new Map() });
    expect(store.get(needsSaveAtom)).toBe(true);
  });

  it("treats a document never written as unsaved", () => {
    const store = createStore();
    connect(store, {
      revision: revision({ saved_etag: null }),
      cells: new Map(),
    });
    expect(store.get(needsSaveAtom)).toBe(true);
  });

  it.each(["pending", "sending", "confirming", "error"] as const)(
    "counts edits the host has not confirmed (%s)",
    (status) => {
      const store = createStore();
      connect(store, { revision: revision(), cells: new Map() }, status);
      expect(store.get(needsSaveAtom)).toBe(true);
    },
  );

  it("ignores a model that is not running", () => {
    const store = createStore();
    connect(store, { revision: revision(), cells: new Map() }, "unavailable");
    expect(store.get(needsSaveAtom)).toBe(false);
  });

  it("compares the layout with the one last saved", () => {
    const store = createStore();
    connect(store, { revision: revision(), cells: new Map() });
    store.set(layoutStateAtom, {
      selectedLayout: "grid",
      layoutData: { grid: null },
    });
    expect(store.get(needsSaveAtom)).toBe(false);
    store.set(savedLayoutAtom, initialLayoutState());
    expect(store.get(needsSaveAtom)).toBe(true);
    store.set(savedLayoutAtom, {
      selectedLayout: "grid",
      layoutData: { grid: null },
    });
    expect(store.get(needsSaveAtom)).toBe(false);
  });
});
