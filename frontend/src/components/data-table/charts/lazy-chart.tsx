/* Copyright 2024 Marimo. All rights reserved. */

import React from "react";
import type { TopLevelSpec } from "vega-lite";
import { tooltipHandler } from "@/components/charts/tooltip";
import { useTheme } from "@/theme/useTheme";
import type { ErrorMessage } from "./chart-spec/spec";
import { augmentSpecWithData } from "./chart-spec/spec";
import { ChartInfoState } from "./components/chart-states";

const LazyVega = React.lazy(() =>
  import("react-vega").then((m) => ({ default: m.Vega })),
);
export const LazyChart: React.FC<{
  baseSpec: TopLevelSpec | ErrorMessage;
  data?: object[];
  height: number;
}> = ({ baseSpec, data, height }) => {
  const { theme } = useTheme();

  if (!data) {
    return <div>No data</div>;
  }

  const renderChart = (specOrMessage: TopLevelSpec | ErrorMessage) => {
    if (typeof specOrMessage === "string") {
      return <ChartInfoState>{specOrMessage}</ChartInfoState>;
    }
    const spec = augmentSpecWithData(specOrMessage, data);

    return (
      <React.Suspense fallback={<LoadingChart />}>
        <LazyVega
          spec={spec}
          theme={theme === "dark" ? "dark" : undefined}
          height={height}
          tooltip={tooltipHandler.call}
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
    <div className="h-full m-auto rounded-md w-full">
      {renderChart(baseSpec)}
    </div>
  );
};

const LoadingChart = () => {
  return <ChartInfoState className="mt-14">Loading chart...</ChartInfoState>;
};
