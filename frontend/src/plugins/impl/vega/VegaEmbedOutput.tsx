/* Copyright 2026 Marimo. All rights reserved. */

import type { JSX } from "react";
import React, { Suspense } from "react";
import { LazyVegaEmbed } from "@/components/charts/lazy";
import { tooltipHandler } from "@/components/charts/tooltip";
import { ChartLoadingState } from "@/components/data-table/charts/components/chart-states";
import type { TopLevelFacetedUnitSpec } from "@/plugins/impl/data-explorer/queries/types";
import type { ResolvedTheme } from "@/theme/useTheme";
import { cn } from "@/utils/cn";
import { vegaContainerClasses } from "./container-size";

/**
 * Wraps LazyVegaEmbed with container-width support.
 * See {@link vegaContainerClasses} for why this is needed.
 */
export const VegaEmbedOutput: React.FC<{
  spec: TopLevelFacetedUnitSpec;
  theme: ResolvedTheme;
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
