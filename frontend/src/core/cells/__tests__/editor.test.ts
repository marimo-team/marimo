/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { describe, expect, it } from "vitest";
import { cellId } from "@/__tests__/branded";
import {
  hideShownCodeAtom,
  isCodeHidden,
  restoredEditorStatesAtom,
  showHiddenCodeAtom,
  shownHiddenCodeAtom,
  takeRestoredEditorStateAtom,
} from "../editor";

const a = cellId("a");
const b = cellId("b");

describe("hidden code showing for now", () => {
  it("hides code unless the cell is showing it", () => {
    const shown = new Set([a]);
    expect(isCodeHidden(true, shown, a)).toBe(false);
    expect(isCodeHidden(true, shown, b)).toBe(true);
    expect(isCodeHidden(false, shown, b)).toBe(false);
    expect(isCodeHidden(undefined, shown, b)).toBe(false);
  });

  it("shows a cell's code and hides it again", () => {
    const store = createStore();
    store.set(showHiddenCodeAtom, { cellId: a });
    expect(store.get(shownHiddenCodeAtom).has(a)).toBe(true);
    store.set(hideShownCodeAtom, { cellId: a });
    expect(store.get(shownHiddenCodeAtom).has(a)).toBe(false);
  });
});

describe("restored editor states", () => {
  it("hands a state over once", () => {
    const store = createStore();
    store.set(restoredEditorStatesAtom, new Map([[a, { doc: "x = 1" }]]));

    store.set(takeRestoredEditorStateAtom, { cellId: a });
    expect(store.get(restoredEditorStatesAtom).size).toBe(0);
  });
});
