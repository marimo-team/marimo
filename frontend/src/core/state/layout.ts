/* Copyright 2023 Marimo. All rights reserved. */
import { GridLayout } from "@/editor/renderers/grid-layout/types";
import { LayoutType } from "@/editor/renderers/types";
import { cellRendererPlugins } from "@/editor/renderers/plugins";
import { Logger } from "@/utils/Logger";
import { atom } from "jotai";
import { getNotebook, notebookCells } from "./cells";
import { store } from "./jotai";

/**
 * The currently selected layout type to show.
 */
export const layoutViewAtom = atom<LayoutType>("vertical");

/**
 * The layout data
 */
export const layoutDataAtom = atom<GridLayout | undefined>(undefined);

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
    (plugin) => plugin.type === layoutViewType
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
