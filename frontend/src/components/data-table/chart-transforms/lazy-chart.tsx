/* Copyright 2024 Marimo. All rights reserved. */

import React from "react";
import type { ChartType } from "./constants";
import { useTheme } from "@/theme/useTheme";

import type { z } from "zod";
import type { ChartSchema } from "./chart-schemas";
import type { TopLevelSpec } from "vega-lite";
import type { ErrorMessage } from "./chart-spec";
import { ChartPieIcon } from "lucide-react";
import { createVegaSpec } from "./chart-spec";

const LazyVega = React.lazy(() =>
  import("react-vega").then((m) => ({ default: m.Vega })),
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

  const specOrMessage = createVegaSpec(
    chartType,
    data,
    formValues,
    theme,
    width,
    height,
  );

  const renderChart = (specOrMessage: TopLevelSpec | ErrorMessage) => {
    if (typeof specOrMessage === "string") {
      return <ChartEmptyState>{specOrMessage}</ChartEmptyState>;
    }

    return (
      <React.Suspense fallback={<LoadingChart />}>
        <LazyVega
          spec={specOrMessage}
          theme={theme === "dark" ? "dark" : undefined}
          height={height}
          actions={{
            export: true,
            source: false,
            compiled: false,
            editor: true,
          }}
        />
      </React.Suspense>
    );
  };

  return (
    <div className="h-full m-auto rounded-md mt-4 w-full">
      {renderChart(specOrMessage)}
    </div>
  );
};

const LoadingChart = () => {
  return <ChartEmptyState>Loading chart...</ChartEmptyState>;
};

const ChartEmptyState = ({ children }: { children: React.ReactNode }) => {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-4">
      <ChartPieIcon className="w-10 h-10 text-muted-foreground" />
      <span className="text-md font-semibold text-muted-foreground">
        {children}
      </span>
    </div>
  );
};
