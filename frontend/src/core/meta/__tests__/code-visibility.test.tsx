/* Copyright 2026 Marimo. All rights reserved. */

import { renderHook } from "@testing-library/react";
import type * as Protocol from "@marimo-team/client/protocol";
import { atom, createStore, Provider } from "jotai";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { partial } from "@/__mocks__/partial";
import { showCodeInRunModeAtom } from "@/core/meta/state";
import { type AppMode, kioskModeAtom, viewStateAtom } from "@/core/mode";
import type { Document, NotebookReplica } from "@/core/notebook/replica";
import {
  remoteAdapter,
  runtimeAdapterAtom,
  staticAdapter,
  type RuntimeAdapter,
} from "@/core/runtime/adapter";
import { activeNotebookReplicaAtom } from "@/core/session/active-notebook";
import { useNotebookCodeAvailable } from "../code-visibility";

interface StoreOpts {
  mode?: AppMode;
  kiosk?: boolean;
  showInRunMode?: boolean;
  runtime?: RuntimeAdapter;
  /** Each cell's source as the host sent it; null is withheld. */
  codes?: ReadonlyArray<string | null>;
}

function document(codes: ReadonlyArray<string | null>): Document {
  const cells = codes.map((code, index): Protocol.Cell => ({
    id: `cell-${index}` as Protocol.CellId,
    notebook_id: "nb",
    code,
    name: "_",
    config: {
      column: null,
      disabled: false,
      hide_code: false,
      expand_output: false,
    },
    etag: `etag-${index}`,
    code_hash: `hash-${index}`,
    version: 1,
  }));
  return {
    revision: {
      notebook_id: "nb",
      order: cells.map((cell) => cell.id),
      app_config: {},
      etag: "etag",
      saved_etag: "etag",
      order_etag: "order",
      app_config_etag: "config",
      version: 1,
    },
    cells: new Map(cells.map((cell) => [cell.id, cell])),
  };
}

function makeStore({
  mode = "read",
  kiosk = false,
  showInRunMode = true,
  runtime = remoteAdapter,
  codes = ["x = 1", ""],
}: StoreOpts = {}) {
  const store = createStore();
  store.set(viewStateAtom, { mode, cellAnchor: null });
  store.set(kioskModeAtom, kiosk);
  store.set(showCodeInRunModeAtom, showInRunMode);
  store.set(runtimeAdapterAtom, runtime);
  store.set(
    activeNotebookReplicaAtom,
    partial<NotebookReplica>(
      { documentAtom: atom(document(codes)) },
      "replica",
    ),
  );
  return store;
}

function render(store: ReturnType<typeof createStore>) {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );
  return renderHook(() => useNotebookCodeAvailable(), { wrapper }).result
    .current;
}

const withheld = [null, null];

const originalHref = window.location.href;

function setSearch(search: string) {
  window.history.replaceState(null, "", `/${search}`);
}

describe("useNotebookCodeAvailable", () => {
  beforeEach(() => {
    setSearch("");
  });

  afterEach(() => {
    window.history.replaceState(null, "", originalHref);
  });

  it("returns true in edit mode regardless of cells", () => {
    expect(render(makeStore({ mode: "edit", codes: withheld }))).toBe(true);
  });

  it("returns true in present mode (only reachable from edit)", () => {
    expect(render(makeStore({ mode: "present", codes: withheld }))).toBe(true);
  });

  it("returns true in kiosk mode even when read mode and no code", () => {
    const store = makeStore({
      mode: "read",
      kiosk: true,
      showInRunMode: false,
      codes: withheld,
    });
    expect(render(store)).toBe(true);
  });

  it("returns true in read mode when at least one cell has code", () => {
    expect(render(makeStore({ mode: "read" }))).toBe(true);
  });

  it("counts an empty cell as code the host sent", () => {
    expect(render(makeStore({ mode: "read", codes: ["", null] }))).toBe(true);
  });

  it("returns false in read mode when the host withheld every source", () => {
    expect(render(makeStore({ mode: "read", codes: withheld }))).toBe(false);
  });

  it("returns false in read mode before a document arrives", () => {
    const store = makeStore({ mode: "read" });
    store.set(activeNotebookReplicaAtom, null);
    expect(render(store)).toBe(false);
  });

  it("returns false in read mode when host opts out via showAppCode", () => {
    expect(render(makeStore({ mode: "read", showInRunMode: false }))).toBe(
      false,
    );
  });

  it("returns false in read mode when ?include-code=false", () => {
    setSearch("?include-code=false");
    expect(render(makeStore({ mode: "read" }))).toBe(false);
  });

  it("ignores ?include-code=false in kiosk mode", () => {
    setSearch("?include-code=false");
    expect(
      render(makeStore({ mode: "read", kiosk: true, codes: withheld })),
    ).toBe(true);
  });

  it("checks embedded code in a static kiosk", () => {
    const options = {
      mode: "read",
      kiosk: true,
      runtime: staticAdapter,
    } as const;
    expect(render(makeStore({ ...options, codes: withheld }))).toBe(false);
    expect(render(makeStore(options))).toBe(true);
  });

  it("returns false for non-edit/non-read modes (home, gallery)", () => {
    for (const mode of ["home", "gallery"] as const) {
      expect(render(makeStore({ mode }))).toBe(false);
    }
  });
});
