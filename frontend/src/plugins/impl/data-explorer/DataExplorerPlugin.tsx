/* Copyright 2024 Marimo. All rights reserved. */
import "../vega/vega.css";

import { z } from "zod";

import { createPlugin } from "@/plugins/core/builder";
import { TooltipProvider } from "@/components/ui/tooltip";
import React from "react";
import type { DataExplorerState } from "./ConnectedDataExplorerComponent";

const LazyDataExplorerComponent = React.lazy(
  () => import("./ConnectedDataExplorerComponent"),
);

export const DataExplorerPlugin = createPlugin<DataExplorerState>(
  "marimo-data-explorer",
)
  .withData(
    z.object({
      label: z.string().nullish(),
      data: z.string(),
    }),
  )
  .renderer((props) => (
    <TooltipProvider>
      <LazyDataExplorerComponent
        {...props.data}
        value={props.value}
        setValue={props.setValue}
      />
    </TooltipProvider>
  ));
