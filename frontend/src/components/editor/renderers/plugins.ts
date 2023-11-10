/* Copyright 2023 Marimo. All rights reserved. */
import { GridLayoutPlugin } from "./grid-layout/grid-layout";
import { ICellRendererPlugin, LayoutType } from "./types";
import { CellData } from "@/core/cells/types";

// If more renderers are added, we may want to consider lazy loading them.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const cellRendererPlugins: Array<ICellRendererPlugin<any, any>> = [
  GridLayoutPlugin,
];

export function deserializeLayout(
  type: LayoutType,
  data: unknown,
  cells: CellData[]
) {
  const plugin = cellRendererPlugins.find((plugin) => plugin.type === type);
  if (plugin === undefined) {
    throw new Error(`Unknown layout type: ${type}`);
  }
  return plugin.deserializeLayout(data, cells);
}
