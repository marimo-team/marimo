/* Copyright 2024 Marimo. All rights reserved. */
import { GridLayoutPlugin } from "./grid-layout/plugin";
import type { ICellRendererPlugin, LayoutType } from "./types";
import type { CellData } from "@/core/cells/types";
import { VerticalLayoutPlugin } from "./vertical-layout/vertical-layout";
import { SlidesLayoutPlugin } from "./slides-layout/plugin";

// If more renderers are added, we may want to consider lazy loading them.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const cellRendererPlugins: Array<ICellRendererPlugin<any, any>> = [
  GridLayoutPlugin,
  SlidesLayoutPlugin,
  VerticalLayoutPlugin,
];

export function deserializeLayout(
  type: LayoutType,
  data: unknown,
  cells: CellData[],
) {
  const plugin = cellRendererPlugins.find((plugin) => plugin.type === type);
  if (plugin === undefined) {
    throw new Error(`Unknown layout type: ${type}`);
  }
  return plugin.deserializeLayout(data, cells);
}
