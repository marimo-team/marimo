/* Copyright 2026 Marimo. All rights reserved. */

import { atom, createStore } from "jotai";
import { describe, expect, it } from "vitest";
import { partial } from "@/__mocks__/partial";
import type { Document, NotebookReplica } from "@/core/notebook/replica";
import { activeNotebookReplicaAtom } from "@/core/session/active-notebook";
import { appConfigAtom, pageAppConfigAtom } from "../config";

function document(app_config: Record<string, unknown>, version = 1): Document {
  return {
    revision: {
      notebook_id: "nb",
      order: [],
      app_config,
      etag: `etag-${version}`,
      saved_etag: null,
      order_etag: "order",
      app_config_etag: "config",
      version,
    },
    cells: new Map(),
  };
}

function connect(store: ReturnType<typeof createStore>, current: Document) {
  store.set(
    activeNotebookReplicaAtom,
    partial<NotebookReplica>({ documentAtom: atom(current) }, "replica"),
  );
}

describe("appConfigAtom", () => {
  it("reads the page's config until the host document arrives", () => {
    const store = createStore();
    expect(store.get(appConfigAtom).width).toBe("medium");
    store.set(pageAppConfigAtom, { width: "full" });
    expect(store.get(appConfigAtom).width).toBe("full");
    connect(store, document({ width: "compact" }));
    expect(store.get(appConfigAtom).width).toBe("compact");
  });

  it("keeps the same object while the record is unchanged", () => {
    const store = createStore();
    connect(store, document({ width: "full" }, 1));
    const first = store.get(appConfigAtom);
    connect(store, document({ width: "full" }, 2));
    expect(store.get(appConfigAtom)).toBe(first);
    connect(store, document({ width: "medium" }, 3));
    expect(store.get(appConfigAtom).width).toBe("medium");
  });
});
