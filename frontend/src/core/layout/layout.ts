/* Copyright 2024 Marimo. All rights reserved. */
import { GridLayout } from "@/components/editor/renderers/grid-layout/types";
import { LayoutType } from "@/components/editor/renderers/types";
import { cellRendererPlugins } from "@/components/editor/renderers/plugins";
import { Logger } from "@/utils/Logger";
import { atom } from "jotai";
import { getNotebook, notebookCells } from "../cells/cells";
import { store } from "../state/jotai";

export type LayoutData = GridLayout | undefined;

/**
 * The currently selected layout type to show.
 */
export const layoutViewAtom = atom<LayoutType>("vertical");

/**
 * The layout data
 */
export const layoutDataAtom = atom<LayoutData>(undefined);

/**
 * Get the serialized layout data, to be used when saving.
 */
export function getSerializedLayout() {
  const notebook = getNotebook();
  const layoutData = store.get(layoutDataAtom);
  const layoutViewType = store.get(layoutViewAtom);

  if (layoutData === undefined) {
    return undefined;
  }
  // Vertical layout has no data, as it is the default.
  if (layoutViewType === "vertical") {
    return undefined;
  }
  const plugin = cellRendererPlugins.find(
    (plugin) => plugin.type === layoutViewType,
  );
  if (plugin === undefined) {
    Logger.error(`Unknown layout type: ${layoutViewType}`);
    return undefined;
  }
  return {
    type: layoutViewType,
    data: plugin.serializeLayout(layoutData, notebookCells(notebook)),
  };
}
