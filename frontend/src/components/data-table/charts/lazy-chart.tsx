/* Copyright 2024 Marimo. All rights reserved. */

import React from "react";
import type { TopLevelSpec } from "vega-lite";
import { LazyVegaEmbed } from "@/components/charts/lazy";
import { tooltipHandler } from "@/components/charts/tooltip";
import { useTheme } from "@/theme/useTheme";
import type { ErrorMessage } from "./chart-spec/spec";
import { augmentSpecWithData } from "./chart-spec/spec";
import { ChartInfoState } from "./components/chart-states";

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
        <LazyVegaEmbed
          spec={spec}
          options={{
            theme: theme === "dark" ? "dark" : undefined,
            height: height,
            actions: {
              export: true,
              source: false,
              compiled: false,
              editor: true,
            },
            mode: "vega",
            tooltip: tooltipHandler.call,
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
