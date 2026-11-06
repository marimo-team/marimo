/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { act, renderHook } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { createElement, type PropsWithChildren } from "react";
import { describe, expect, it } from "vitest";
import { cellId } from "@/__tests__/branded";
import {
  hideShownCodeAtom,
  isCodeHidden,
  restoredEditorStatesAtom,
  showHiddenCodeAtom,
  shownHiddenCodeAtom,
  takeRestoredEditorStateAtom,
  useRestoredEditorState,
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

  it("shows a cell's code and hides it again, saying whether it was showing", () => {
    const store = createStore();
    store.set(showHiddenCodeAtom, { cellId: a });
    expect(store.get(shownHiddenCodeAtom).has(a)).toBe(true);
    expect(store.set(hideShownCodeAtom, { cellId: a })).toBe(true);
    expect(store.get(shownHiddenCodeAtom).has(a)).toBe(false);
    expect(store.set(hideShownCodeAtom, { cellId: a })).toBe(false);
  });
});

describe("restored editor states", () => {
  it("hands a state over once", () => {
    const store = createStore();
    store.set(restoredEditorStatesAtom, new Map([[a, { doc: "x = 1" }]]));
    const wrapper = ({ children }: PropsWithChildren) =>
      createElement(Provider, { store }, children);
    const { result } = renderHook(() => useRestoredEditorState(a), {
      wrapper,
    });
    expect(result.current).toEqual({ doc: "x = 1" });

    act(() => store.set(takeRestoredEditorStateAtom, { cellId: a }));

    expect(result.current).toBeNull();
    expect(store.get(restoredEditorStatesAtom).size).toBe(0);
  });
});
