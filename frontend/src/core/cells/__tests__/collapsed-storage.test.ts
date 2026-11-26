/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { afterEach, describe, expect, it } from "vitest";
import { cellId } from "@/__tests__/branded";
import { exportedForTesting, notebookAtom } from "../cells";
import {
  type CollapsedHeadingsStorage,
  followCollapsedHeadings,
  headingKeys,
} from "../collapsed-storage";
import type { CellId } from "../ids";
import { collapsedAtom } from "../layout";
import type { Outline } from "../outline";
import { createCellRuntimeState } from "../types";

function heading(name: string, level = 1): Outline {
  return { items: [{ name, level, by: { id: name } }] };
}

class MemoryStorage implements CollapsedHeadingsStorage {
  public values = new Map<string, string[]>();
  public get(key: string) {
    return this.values.get(key) ?? [];
  }
  public set(key: string, value: string[]) {
    this.values.set(key, value);
  }
  public saved() {
    return [...this.values.values()][0] ?? [];
  }
}

describe("headingKeys", () => {
  const [a, b, c, d, e] = ["a", "b", "c", "d", "e"].map(cellId);
  const outlines = new Map<CellId, Outline>([
    [a, heading("Intro")],
    [c, heading("Intro")],
    [d, heading("Intro", 2)],
    [e, heading("Deep", 4)],
  ]);

  it("keys headers by level, text and occurrence", () => {
    const keys = headingKeys([a, b, c, d, e], (id) => outlines.get(id));
    expect([...keys]).toEqual([
      [a, "1:Intro#0"],
      [c, "1:Intro#1"],
      [d, "2:Intro#0"],
    ]);
  });

  it("keeps a header's key when an unrelated header is removed", () => {
    const before = headingKeys([a, c, d], (id) => outlines.get(id));
    const after = headingKeys([a, d], (id) => outlines.get(id));
    expect(after.get(d)).toBe(before.get(d));
  });
});

describe("followCollapsedHeadings", () => {
  const stops: Array<() => void> = [];
  afterEach(() => {
    for (const stop of stops.splice(0)) {
      stop();
    }
  });

  function setup(storage: CollapsedHeadingsStorage) {
    const store = createStore();
    store.set(notebookAtom, exportedForTesting.initialNotebookState());
    const controller = new AbortController();
    stops.push(() => controller.abort());
    followCollapsedHeadings({ store, signal: controller.signal, storage });
    const setOutlines = (cells: Array<[CellId, Outline | null]>) =>
      store.set(notebookAtom, (state) => ({
        ...state,
        cellIds: cells.map(([id]) => id),
        cellRuntime: Object.fromEntries(
          cells.map(([id, outline]) => [
            id,
            { ...createCellRuntimeState(), outline },
          ]),
        ),
      }));
    return { store, setOutlines };
  }

  it("saves folded headers by heading", () => {
    const storage = new MemoryStorage();
    const { store, setOutlines } = setup(storage);
    const [h1, x, h2] = ["h1", "x", "h2"].map(cellId);
    setOutlines([
      [h1, heading("One")],
      [x, null],
      [h2, heading("Two")],
    ]);
    store.set(collapsedAtom, new Set([h2]));
    expect(storage.saved()).toEqual(["1:Two#0"]);
    store.set(collapsedAtom, new Set());
    expect(storage.saved()).toEqual([]);
  });

  it("refolds saved headers as their outlines arrive after a reload", () => {
    const storage = new MemoryStorage();
    storage.set("marimo:collapsed-headings", ["1:Two#0"]);
    const { store, setOutlines } = setup(storage);
    expect(store.get(collapsedAtom).size).toBe(0);

    // New cell ids, as after a reload; the outline arrives once cells run.
    const [h1, h2] = ["new-h1", "new-h2"].map(cellId);
    setOutlines([
      [h1, heading("One")],
      [h2, null],
    ]);
    expect(store.get(collapsedAtom).size).toBe(0);
    expect(storage.saved()).toEqual(["1:Two#0"]);

    setOutlines([
      [h1, heading("One")],
      [h2, heading("Two")],
    ]);
    expect([...store.get(collapsedAtom)]).toEqual([h2]);
    expect(storage.saved()).toEqual(["1:Two#0"]);
  });

  it("does not refold a restored header the user unfolded", () => {
    const storage = new MemoryStorage();
    storage.set("marimo:collapsed-headings", ["1:One#0"]);
    const { store, setOutlines } = setup(storage);
    const h1 = cellId("h1");
    setOutlines([[h1, heading("One")]]);
    expect(store.get(collapsedAtom).has(h1)).toBe(true);

    store.set(collapsedAtom, new Set());
    setOutlines([[h1, heading("One")]]);
    expect(store.get(collapsedAtom).size).toBe(0);
    expect(storage.saved()).toEqual([]);
  });

  it("saves a folded header under its new text when renamed", () => {
    const storage = new MemoryStorage();
    const { store, setOutlines } = setup(storage);
    const h1 = cellId("h1");
    setOutlines([[h1, heading("Old")]]);
    store.set(collapsedAtom, new Set([h1]));
    expect(storage.saved()).toEqual(["1:Old#0"]);

    setOutlines([[h1, heading("New")]]);
    expect(storage.saved()).toEqual(["1:New#0"]);
  });
});
