/* Copyright 2023 Marimo. All rights reserved. */
import { AppConfig } from "@/core/config/config";
import { CellState } from "@/core/model/cells";
import { ZodType, ZodTypeDef } from "zod";
import { AppMode } from "@/core/mode";

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
  cells: CellState[];

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

export type LayoutType = "grid" | "vertical";

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

  deserializeLayout: (layout: S, cells: CellState[]) => L;
  serializeLayout: (layout: L, cells: CellState[]) => S;

  Component: React.FC<ICellRendererProps<L>>;

  getInitialLayout: (cells: CellState[]) => L;
}
