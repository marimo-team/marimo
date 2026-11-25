/* Copyright 2026 Marimo. All rights reserved. */
import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterEach, expect, it, vi } from "vitest";
import { cellId, variableName } from "@/__tests__/branded";
import { store } from "@/core/state/jotai";
import { variablesAtom } from "@/core/variables/state";
import {
  reactiveReferencesBundle,
  reactiveReferencesField,
} from "../extension";

let view: EditorView;
afterEach(() => {
  view?.destroy();
  vi.useRealTimers();
  store.set(variablesAtom, {});
});

it("skips unchanged ranges, updates edited ranges, and clears removed references", async () => {
  vi.useFakeTimers();
  store.set(variablesAtom, {});
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
  const variables = {
    [variableName("value")]: {
      name: variableName("value"),
      declaredBy: [cellId("cell2")],
      usedBy: [cellId("cell1")],
    },
  };
  store.set(variablesAtom, variables);
  await flush();
  expect(view.state.field(reactiveReferencesField).ranges).toEqual([
    { from: 0, to: 5, variableName: "value" },
  ]);
  dispatch.mockClear();
  store.set(variablesAtom, { ...variables });
  await flush();
  expect(dispatch).not.toHaveBeenCalled();
  view.dispatch({ changes: { from: 0, insert: " " } });
  await flush();
  expect(view.state.field(reactiveReferencesField).ranges[0].from).toBe(1);
  store.set(variablesAtom, {});
  await flush();
  expect(view.state.field(reactiveReferencesField).ranges).toEqual([]);
});
