/* Copyright 2026 Marimo. All rights reserved. */
import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterEach, expect, it, vi } from "vitest";
import { setNotebookAnalysis } from "@/__tests__/notebook-analysis";
import { cellId } from "@/__tests__/branded";
import { activeNotebookReplicaAtom } from "@/core/session/active-notebook";
import { store } from "@/core/state/jotai";
import {
  reactiveReferencesBundle,
  reactiveReferencesField,
} from "../extension";

let view: EditorView;
afterEach(() => {
  view?.destroy();
  vi.useRealTimers();
  store.set(activeNotebookReplicaAtom, null);
});

it("skips unchanged ranges, updates edited ranges, and clears removed references", async () => {
  vi.useFakeTimers();
  view = new EditorView({
    state: EditorState.create({
      doc: "value",
      extensions: [python(), reactiveReferencesBundle(cellId("cell1"), true)],
    }),
    parent: document.body,
  });
  const dispatch = vi.spyOn(view, "dispatch");
  const flush = async () => {
    vi.advanceTimersByTime(300);
    await Promise.resolve();
  };
  await flush();
  expect(dispatch).not.toHaveBeenCalled();
  const cells = { cell2: { defs: ["value"] }, cell1: { refs: ["value"] } };
  setNotebookAnalysis(store, cells);
  await flush();
  expect(view.state.field(reactiveReferencesField).ranges).toEqual([
    { from: 0, to: 5, variableName: "value" },
  ]);
  dispatch.mockClear();
  setNotebookAnalysis(store, cells);
  await flush();
  expect(dispatch).not.toHaveBeenCalled();
  view.dispatch({ changes: { from: 0, insert: " " } });
  await flush();
  expect(view.state.field(reactiveReferencesField).ranges[0].from).toBe(1);
  setNotebookAnalysis(store, {});
  await flush();
  expect(view.state.field(reactiveReferencesField).ranges).toEqual([]);
});
