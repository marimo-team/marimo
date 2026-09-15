/* Copyright 2026 Marimo. All rights reserved. */

import type { CellData } from "@/core/cells/types";
import { Logger } from "@/utils/Logger";
import { GridLayoutPlugin } from "./grid-layout/plugin";
import { SlidesLayoutPlugin } from "./slides-layout/plugin";
import type { ICellRendererPlugin, LayoutType } from "./types";
import { VerticalLayoutPlugin } from "./vertical-layout/vertical-layout";

// If more renderers are added, we may want to consider lazy loading them.
// oxlint-disable-next-line typescript/no-explicit-any
export const cellRendererPlugins: ICellRendererPlugin<any, any>[] = [
  GridLayoutPlugin,
  SlidesLayoutPlugin,
  VerticalLayoutPlugin,
];

export function deserializeLayout({
  type,
  data,
  cells,
}: {
  type: LayoutType;
  data: unknown;
  cells: CellData[];
}) {
  const plugin = cellRendererPlugins.find((plugin) => plugin.type === type);
  if (plugin === undefined) {
    throw new Error(`Unknown layout type: ${type}`);
  }
  const parsed = plugin.validator.safeParse(data);
  if (!parsed.success) {
    Logger.warn(`Invalid ${type} layout`, parsed.error);
    return plugin.getInitialLayout(cells);
  }
  return plugin.deserializeLayout(parsed.data, cells);
}
