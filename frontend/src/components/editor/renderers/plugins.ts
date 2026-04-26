/* Copyright 2026 Marimo. All rights reserved. */

import type { CellData } from "@/core/cells/types";
import { Logger } from "@/utils/Logger";
import { GridLayoutPlugin } from "./grid-layout/plugin";
import type { GridLayout, SerializedGridLayout } from "./grid-layout/types";
import { SlidesLayoutPlugin } from "./slides-layout/plugin";
import type {
  SerializedSlidesLayout,
  SlidesLayout,
} from "./slides-layout/types";
import type { ICellRendererPlugin, LayoutType } from "./types";
import type {
  SerializedVerticalLayout,
  VerticalLayout,
} from "./vertical-layout/types.ts";
import { VerticalLayoutPlugin } from "./vertical-layout/vertical-layout";

export interface LayoutDataByType {
  vertical: VerticalLayout;
  grid: GridLayout;
  slides: SlidesLayout;
}

interface SerializedLayoutDataByType {
  vertical: SerializedVerticalLayout;
  grid: SerializedGridLayout;
  slides: SerializedSlidesLayout;
}

type CellRendererPluginByType = {
  [K in LayoutType]: ICellRendererPlugin<
    SerializedLayoutDataByType[K],
    LayoutDataByType[K]
  >;
};

// If more renderers are added, we may want to consider lazy loading them.
const cellRendererPluginMap: CellRendererPluginByType = {
  vertical: VerticalLayoutPlugin,
  grid: GridLayoutPlugin,
  slides: SlidesLayoutPlugin,
};

export function getCellRendererPlugin<K extends LayoutType>(
  type: K,
): CellRendererPluginByType[K] {
  return cellRendererPluginMap[type];
}

export function deserializeLayout<K extends LayoutType>({
  type,
  data,
  cells,
}: {
  type: K;
  data: unknown;
  cells: CellData[];
}): LayoutDataByType[K] {
  const plugin = getCellRendererPlugin(type);
  const result = plugin.validator.safeParse(data);
  if (!result.success) {
    Logger.warn(
      `Invalid serialized layout for "${type}"; falling back to default.`,
      result.error,
    );
    return plugin.getInitialLayout(cells);
  }
  return plugin.deserializeLayout(result.data, cells);
}
