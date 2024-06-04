/* Copyright 2024 Marimo. All rights reserved. */
import React, { useContext } from "react";
import { ColumnChartSpecModel } from "./chart-spec-model";
import { useTheme } from "@/theme/useTheme";
import { prettyScientificNumber } from "@/utils/numbers";
import { prettyDate } from "@/utils/dates";
import { DelayMount } from "../utils/delay-mount";
import { ChartSkeleton } from "../charts/chart-skeleton";

export const ColumnChartContext = React.createContext<
  ColumnChartSpecModel<unknown>
>(ColumnChartSpecModel.EMPTY);

interface Props<TData, TValue> {
  columnId: string;
}

const LazyVegaLite = React.lazy(() =>
  import("react-vega").then((m) => ({ default: m.VegaLite })),
);

export const TableColumnSummary = <TData, TValue>({
  columnId,
}: Props<TData, TValue>) => {
  const chartSpecModel = useContext(ColumnChartContext);
  const { theme } = useTheme();
  const { spec, type, summary } = chartSpecModel.getHeaderSummary(columnId);

  let chart: React.ReactNode = null;
  if (spec) {
    chart = (
      <DelayMount
        milliseconds={200}
        fallback={<ChartSkeleton seed={columnId} width={130} height={60} />}
      >
        <LazyVegaLite
          spec={spec}
          width={120}
          height={50}
          style={{ minWidth: "unset", maxHeight: "60px" }}
          actions={false}
          theme={theme === "dark" ? "dark" : "vox"}
        />
      </DelayMount>
    );
  }

  const renderStats = () => {
    if (!summary) {
      return null;
    }

    switch (type) {
      case "date":
        return (
          <div className="flex justify-between w-full px-2 whitespace-pre">
            <span>{prettyDate(summary.min)}</span>-
            <span>{prettyDate(summary.max)}</span>
          </div>
        );
      case "integer":
      case "number":
        if (
          typeof summary.min === "number" &&
          typeof summary.max === "number"
        ) {
          return (
            <div className="flex justify-between w-full px-2 whitespace-pre">
              <span>{prettyScientificNumber(summary.min)}</span>
              <span>{prettyScientificNumber(summary.max)}</span>
            </div>
          );
        }
        return (
          <div className="flex justify-between w-full px-2 whitespace-pre">
            <span>{summary.min}</span>
            <span>{summary.max}</span>
          </div>
        );
      case "boolean":
        return (
          <div>
            <span className="whitespace-pre">nulls: {summary.nulls}</span>
          </div>
        );
      case "string":
        return (
          <div className="flex flex-col">
            <span className="whitespace-pre">unique: {summary.unique}</span>
            <span className="whitespace-pre">nulls: {summary.nulls}</span>
          </div>
        );
      case "unknown":
        return (
          <div>
            <span className="whitespace-pre">nulls: {summary.nulls}</span>
          </div>
        );
    }
  };

  return (
    <div className="flex flex-col items-center text-xs text-muted-foreground align-end">
      {chart}
      {renderStats()}
    </div>
  );
};
