/* Copyright 2024 Marimo. All rights reserved. */
import { ICellRendererPlugin } from "../types";
import { SlidesLayout } from "./types";
import { z } from "zod";
import { SlidesLayoutRenderer } from "./slides-layout";

/**
 * Plugin definition for the slides layout.
 */
export const SlidesLayoutPlugin: ICellRendererPlugin<
  SlidesLayout,
  SlidesLayout
> = {
  type: "slides",
  name: "Slides",

  validator: z.object({}),

  deserializeLayout: (_serialized, _cells): SlidesLayout => {
    return {};
  },

  serializeLayout: (_layout, _cells): SlidesLayout => {
    return {};
  },

  Component: SlidesLayoutRenderer,

  getInitialLayout: () => ({}),
};
