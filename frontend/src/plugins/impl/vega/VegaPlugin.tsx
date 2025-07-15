/* Copyright 2024 Marimo. All rights reserved. */

import { z } from "zod";
import type { IPlugin, IPluginProps } from "@/plugins/types";
import type { VegaLiteSpec } from "./types";

import type { Data, VegaComponentState } from "./vega-component";

import "./vega.css";
import React, { type JSX } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";

const LazyVegaComponent = React.lazy(() => import("./vega-component"));

export class VegaPlugin implements IPlugin<VegaComponentState, Data> {
  tagName = "marimo-vega";

  validator = z.object({
    spec: z
      .object({})
      .passthrough()
      .transform((spec) => spec as unknown as VegaLiteSpec),
    chartSelection: z
      .union([z.boolean(), z.literal("point"), z.literal("interval")])
      .default(true),
    fieldSelection: z.union([z.boolean(), z.array(z.string())]).default(true),
  });

  render(props: IPluginProps<VegaComponentState, Data>): JSX.Element {
    return (
      <TooltipProvider>
        <LazyVegaComponent
          value={props.value}
          setValue={props.setValue}
          {...props.data}
        />
      </TooltipProvider>
    );
  }
}
