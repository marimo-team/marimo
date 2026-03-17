/* Copyright 2026 Marimo. All rights reserved. */

import type { JSX } from "react";
import React, { Suspense } from "react";
import { tooltipHandler } from "@/components/charts/tooltip";
import type { TopLevelFacetedUnitSpec } from "@/plugins/impl/data-explorer/queries/types";
import { vegaContainerClasses } from "@/plugins/impl/vega/container-size";
import { cn } from "@/utils/cn";
import { ChartLoadingState } from "../data-table/charts/components/chart-states";

export const LazyVegaEmbed = React.lazy(() =>
  import("react-vega").then((m) => ({ default: m.VegaEmbed })),
);

/**
 * Wraps LazyVegaEmbed with container-width support.
 * See {@link vegaContainerClasses} for why this is needed.
 */
export const VegaEmbedOutput: React.FC<{
  spec: TopLevelFacetedUnitSpec;
  theme: string;
}> = ({ spec, theme }): JSX.Element => {
  return (
    <Suspense fallback={<ChartLoadingState />}>
      <div className={cn(vegaContainerClasses(spec))}>
        <LazyVegaEmbed
          spec={spec}
          options={{
            theme: theme === "dark" ? "dark" : undefined,
            mode: "vega-lite",
            tooltip: tooltipHandler.call,
            renderer: "canvas",
          }}
        />
      </div>
    </Suspense>
  );
};
