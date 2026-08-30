/* Copyright 2026 Marimo. All rights reserved. */

import {
  cellRendererPlugins,
  deserializeLayout,
} from "@/components/editor/renderers/plugins";
import type { ICellRendererPlugin } from "@/components/editor/renderers/types";
import { Logger } from "@/utils/Logger";
import { getNotebook } from "../cells/cells";
import type { CellData } from "../cells/types";
import { notebookCells } from "../cells/utils";
import { store } from "../state/jotai";
import {
  initialLayoutState,
  layoutStateAtom,
  type LayoutState,
  type SerializedLayout,
} from "./state";

export {
  initialLayoutState,
  layoutStateAtom,
  type LayoutData,
  type LayoutState,
  resolveLayoutType,
  type SerializedLayout,
  useLayoutActions,
  useLayoutState,
} from "./state";

export function deserializeLayoutState(
  layout: SerializedLayout | null | undefined,
  cells: CellData[],
): LayoutState {
  if (layout == null) {
    return initialLayoutState();
  }

  const plugin = cellRendererPlugins.find(
    (candidate) => candidate.type === layout.type,
  );
  if (plugin === undefined) {
    Logger.warn(`Unknown layout type: ${layout.type}`);
    return initialLayoutState();
  }

  return {
    selectedLayout: plugin.type,
    layoutData: {
      [plugin.type]: deserializeLayout({
        type: plugin.type,
        data: layout.data,
        cells,
      }),
    },
  };
}

export function resolveLayoutData<S, L>({
  state,
  plugin,
  cells,
}: {
  state: LayoutState;
  plugin: ICellRendererPlugin<S, L>;
  cells: CellData[];
}): L {
  const materialized = state.layoutData[plugin.type];
  if (materialized !== undefined) {
    return materialized as L;
  }
  if (state.pendingLayout?.type === plugin.type) {
    return deserializeLayout({
      type: plugin.type,
      data: state.pendingLayout.data,
      cells,
    }) as L;
  }
  return plugin.getInitialLayout(cells);
}

/**
 * Get the serialized layout data, to be used when saving.
 */
export function getSerializedLayout() {
  const notebook = getNotebook();
  const layoutState = store.get(layoutStateAtom);
  const { selectedLayout } = layoutState;

  // Vertical layout has no data, as it is the default.
  if (selectedLayout === "vertical") {
    return null;
  }

  const plugin = cellRendererPlugins.find(
    (plugin) => plugin.type === selectedLayout,
  );
  if (plugin === undefined) {
    Logger.error(`Unknown layout type: ${selectedLayout}`);
    return null;
  }
  const cells = notebookCells(notebook);
  const data = resolveLayoutData({ state: layoutState, plugin, cells });
  return {
    type: selectedLayout,
    data: plugin.serializeLayout(data, cells),
  };
}
