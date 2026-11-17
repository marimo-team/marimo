/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { expect, it } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { notebookAtom } from "@/core/cells/cells";
import { CellId } from "@/core/cells/ids";
import { getAIContextRegistry } from "../../context";
import { CellContextProvider } from "../cell";

it("resolves empty cells and reads their latest code when preparing context", () => {
  const store = createStore();
  const cellId = CellId.create();
  const provider = new CellContextProvider(store);
  store.set(
    notebookAtom,
    MockNotebook.notebookState({ cellData: { [cellId]: { code: "" } } }),
  );
  const uri = provider.asURI(cellId);
  expect(getAIContextRegistry(store).formatContextForAI([uri])).toContain(
    "This cell is empty.",
  );
  store.set(
    notebookAtom,
    MockNotebook.notebookState({ cellData: { [cellId]: { code: "x = 1" } } }),
  );
  expect(getAIContextRegistry(store).formatContextForAI([uri])).toContain(
    "x = 1",
  );
  store.set(notebookAtom, MockNotebook.notebookState());
  expect(getAIContextRegistry(store).formatContextForAI([uri])).toBe("");
});

it("completes cell names while inserting stable cell references", () => {
  const store = createStore();
  const cellId = CellId.create();
  store.set(
    notebookAtom,
    MockNotebook.notebookState({
      cellData: { [cellId]: { name: "my_analysis", code: "x = 1" } },
    }),
  );
  const provider = new CellContextProvider(store);
  expect(provider.formatCompletion(provider.getItems()[0])).toMatchObject({
    label: "@my_analysis",
    displayLabel: "my_analysis",
    apply: `@cell://${cellId}`,
  });
});
