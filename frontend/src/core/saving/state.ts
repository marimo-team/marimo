/* Copyright 2024 Marimo. All rights reserved. */
import { atom } from "jotai";
import { type LayoutState, layoutStateAtom } from "../layout/layout";
import type { CellConfig } from "../network/types";
import { arrayShallowEquals } from "@/utils/arrays";
import { isEqual } from "lodash-es";
import { notebookAtom, type NotebookState } from "../cells/cells";

export interface LastSavedNotebook {
  codes: string[];
  configs: CellConfig[];
  names: string[];
  layout: LayoutState;
}

export const lastSavedNotebookAtom = atom<LastSavedNotebook | undefined>(
  undefined,
);

export const needsSaveAtom = atom((get) => {
  const lastSavedNotebook = get(lastSavedNotebookAtom);
  const state = get(notebookAtom);
  const layout = get(layoutStateAtom);
  return notebookNeedsSave(state, layout, lastSavedNotebook);
});

export function notebookNeedsSave(
  state: NotebookState,
  layout: LayoutState,
  lastSavedNotebook: LastSavedNotebook | undefined,
) {
  if (!lastSavedNotebook) {
    return false;
  }
  const { cellIds, cellData } = state;
  const data = cellIds.inOrderIds.map((cellId) => cellData[cellId]);
  const codes = data.map((d) => d.code);
  const configs = data.map((d) => d.config);
  const names = data.map((d) => d.name);
  return (
    !arrayShallowEquals(codes, lastSavedNotebook.codes) ||
    !arrayShallowEquals(names, lastSavedNotebook.names) ||
    !isEqual(configs, lastSavedNotebook.configs) ||
    !isEqual(layout.selectedLayout, lastSavedNotebook.layout.selectedLayout) ||
    !isEqual(layout.layoutData, lastSavedNotebook.layout.layoutData)
  );
}
