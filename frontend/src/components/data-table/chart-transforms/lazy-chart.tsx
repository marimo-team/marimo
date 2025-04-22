/* Copyright 2024 Marimo. All rights reserved. */

import React from "react";
import type { ChartType } from "./constants";
import { useTheme } from "@/theme/useTheme";

import type { z } from "zod";
import type { ChartSchema } from "./chart-schemas";
import type { TopLevelSpec } from "vega-lite";
import type { ResolvedTheme } from "@/theme/useTheme";
import type { ErrorMessage } from "./chart-spec";
import { ChartPieIcon } from "lucide-react";

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
      children: (spec: TopLevelSpec | ErrorMessage) => React.ReactNode;
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
      <React.Suspense fallback={<LoadingChart />}>
        <LazyChartSpec
          chartType={chartType}
          data={data}
          formValues={formValues}
          theme={theme}
          width={width}
          height={height}
        >
          {(specOrMessage) => {
            if (typeof specOrMessage === "string") {
              return (
                <div className="h-full flex flex-col items-center justify-center gap-2">
                  <ChartPieIcon className="w-8 h-8 text-muted-foreground" />
                  <span className="text-md font-semibold text-muted-foreground">
                    {specOrMessage}
                  </span>
                </div>
              );
            }

            return (
              <React.Suspense fallback={<LoadingChart />}>
                <LazyVega
                  spec={specOrMessage}
                  theme={theme === "dark" ? "dark" : undefined}
                  actions={{
                    export: true,
                    source: false,
                    compiled: false,
                    editor: true,
                  }}
                />
              </React.Suspense>
            );
          }}
        </LazyChartSpec>
      </React.Suspense>
    </div>
  );
};

const LoadingChart = () => {
  return (
    <div className="h-full flex items-center justify-center gap-2">
      <ChartPieIcon className="w-6 h-6" />
      <span className="text-md">Loading chart...</span>
    </div>
  );
};
