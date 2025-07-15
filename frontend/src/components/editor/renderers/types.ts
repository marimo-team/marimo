/* Copyright 2024 Marimo. All rights reserved. */

import type { ZodType, ZodTypeDef } from "zod";
import type { CellData, CellRuntimeState } from "@/core/cells/types";
import type { AppConfig } from "@/core/config/config-schema";
import type { AppMode } from "@/core/mode";

/**
 * The props passed to a cell renderer.
 */
export interface ICellRendererProps<L> {
  /**
   * App Config
   */
  appConfig: AppConfig;

  /**
   * The cells to render.
   */
  cells: Array<CellRuntimeState & CellData>;

  /**
   * The layout configuration.
   */
  layout: L;

  /**
   * Application mode.
   * As of now, this won't include 'edit' mode.
   */
  mode: AppMode;

  /**
   * Callback to set the layout.
   * @param layout The new layout.
   */
  setLayout: (layout: L) => void;
}

export type LayoutType = "vertical" | "grid" | "slides";
/**
 * List of supported layout types, in the order to be displayed.
 */
export const LAYOUT_TYPES: LayoutType[] = ["vertical", "grid", "slides"];
/**
 * Overridable layout types.
 * These types can override the current layout via a URL parameter.
 */
export const OVERRIDABLE_LAYOUT_TYPES: LayoutType[] = ["slides"];

/**
 * A cell renderer plugin.
 * @template S The layout as stored at rest, in its serialized form.
 * @template L The layout as used by the renderer.
 *
 * We have 2 different forms since cells don't have IDs at rest.
 * The mapping allows us to map between indexed-based cells and ID-based cells.
 */
export interface ICellRendererPlugin<S, L> {
  type: LayoutType;

  name: string;

  /**
   * Validate the layout data. Use [zod](https://zod.dev/) to validate the data.
   */
  validator: ZodType<S, ZodTypeDef, unknown>;

  deserializeLayout: (layout: S, cells: CellData[]) => L;
  serializeLayout: (layout: L, cells: CellData[]) => S;

  Component: React.FC<ICellRendererProps<L>>;

  getInitialLayout: (cells: CellData[]) => L;
}
