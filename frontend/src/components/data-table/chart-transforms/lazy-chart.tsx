/* Copyright 2024 Marimo. All rights reserved. */

import React from "react";
import type { ChartType } from "./storage";
import { useTheme } from "@/theme/useTheme";

import type { z } from "zod";
import type { ChartSchema } from "./chart-schemas";
import type { TopLevelSpec } from "vega-lite";
import type { ResolvedTheme } from "@/theme/useTheme";

const LazyVega = React.lazy(() =>
  import("react-vega").then((m) => ({ default: m.Vega })),
);

const LazyChartSpec = React.lazy(() =>
  import("./chart-spec").then((m) => ({
    default: (props: {
      chartType: ChartType;
      data: object[];
      formValues: z.infer<typeof ChartSchema>;
      theme: ResolvedTheme;
      width: number | "container";
      height: number;
      children: (spec: TopLevelSpec | null) => React.ReactNode;
    }) => {
      const spec = m.createVegaSpec(
        props.chartType,
        props.data,
        props.formValues,
        props.theme,
        props.width,
        props.height,
      );
      return props.children(spec);
    },
  })),
);

export const LazyChart: React.FC<{
  chartType: ChartType;
  formValues: z.infer<typeof ChartSchema>;
  data?: object[];
  width: number | "container";
  height: number;
}> = ({ chartType, formValues, data, width, height }) => {
  const { theme } = useTheme();

  if (!data) {
    return <div>No data</div>;
  }

  return (
    <div className="h-full m-auto rounded-md mt-4 w-full">
      <React.Suspense fallback={<div>Loading chart...</div>}>
        <LazyChartSpec
          chartType={chartType}
          data={data}
          formValues={formValues}
          theme={theme}
          width={width}
          height={height}
        >
          {(vegaSpec) => {
            if (!vegaSpec) {
              return <div>This configuration is not supported</div>;
            }

            return (
              <React.Suspense fallback={<div>Loading Vega...</div>}>
                <LazyVega
                  spec={vegaSpec}
                  theme={theme === "dark" ? "dark" : undefined}
                />
              </React.Suspense>
            );
          }}
        </LazyChartSpec>
      </React.Suspense>
    </div>
  );
};
