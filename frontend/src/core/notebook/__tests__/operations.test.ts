/* Copyright 2026 Marimo. All rights reserved. */

import type { NotebookOutput } from "@marimo-team/client/protocol";
import { atom, createStore } from "jotai";
import { describe, expect, it } from "vitest";
import { partial } from "@/__mocks__/partial";
import { kioskModeAtom } from "@/core/mode";
import type { NotebookReplica } from "@/core/notebook/replica";
import { activeNotebookReplicaAtom } from "@/core/session/active-notebook";
import { canEditAtom, notebookOperationsAtom } from "../operations";

function connect(
  store: ReturnType<typeof createStore>,
  operations: readonly string[] | null,
) {
  const notebook =
    operations === null
      ? null
      : ({ id: "nb", operations } as unknown as NotebookOutput);
  store.set(
    activeNotebookReplicaAtom,
    partial<NotebookReplica>({ notebookAtom: atom(notebook) }, "replica"),
  );
}

describe("notebook operations", () => {
  it("advertises nothing until the notebook is ready", () => {
    const store = createStore();
    expect(store.get(notebookOperationsAtom)).toEqual([]);
    expect(store.get(canEditAtom)).toBe(false);
    connect(store, null);
    expect(store.get(canEditAtom)).toBe(false);
  });

  it("allows editing when the host lists notebook.edit", () => {
    const store = createStore();
    connect(store, ["notebook.edit", "runtime.run"]);
    expect(store.get(canEditAtom)).toBe(true);
    connect(store, ["runtime.run"]);
    expect(store.get(canEditAtom)).toBe(false);
  });

  it("withholds editing from a kiosk connection", () => {
    const store = createStore();
    connect(store, ["notebook.edit"]);
    store.set(kioskModeAtom, true);
    expect(store.get(canEditAtom)).toBe(false);
    store.set(kioskModeAtom, false);
    expect(store.get(canEditAtom)).toBe(true);
  });
});
