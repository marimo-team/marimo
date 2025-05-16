/* Copyright 2024 Marimo. All rights reserved. */

import React from "react";
import { useTheme } from "@/theme/useTheme";
import type { TopLevelSpec } from "vega-lite";
import type { ErrorMessage } from "./chart-spec/spec";
import { ChartPieIcon } from "lucide-react";
import { augmentSpecWithData } from "./chart-spec/spec";

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
      return <ChartEmptyState>{specOrMessage}</ChartEmptyState>;
    }
    const spec = augmentSpecWithData(specOrMessage, data);

    return (
      <React.Suspense fallback={<LoadingChart />}>
        <LazyVega
          spec={spec}
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
    <div className="h-full m-auto rounded-md w-full">
      {renderChart(baseSpec)}
    </div>
  );
};

const LoadingChart = () => {
  return <ChartEmptyState>Loading chart...</ChartEmptyState>;
};

const ChartEmptyState = ({ children }: { children: React.ReactNode }) => {
  return (
    <div className="flex flex-col items-center justify-center gap-4 mt-14">
      <ChartPieIcon className="w-10 h-10 text-muted-foreground" />
      <span className="text-md font-semibold text-muted-foreground">
        {children}
      </span>
    </div>
  );
};
