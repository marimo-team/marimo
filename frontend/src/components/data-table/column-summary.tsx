/* Copyright 2024 Marimo. All rights reserved. */
import React, { useContext } from "react";
import { ColumnChartSpecModel } from "./chart-spec-model";
import { useTheme } from "@/theme/useTheme";
import { prettyNumber, prettyScientificNumber } from "@/utils/numbers";
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
        // Without a chart
        if (!spec) {
          return (
            <div className="flex flex-col whitespace-pre">
              <span>min: {prettyDate(summary.min)}</span>
              <span>max: {prettyDate(summary.max)}</span>
              <span>unique: {prettyNumber(summary.unique)}</span>
              <span>nulls: {prettyNumber(summary.nulls)}</span>
            </div>
          );
        }

        return (
          <div className="flex justify-between w-full px-2 whitespace-pre">
            <span>{prettyDate(summary.min)}</span>-
            <span>{prettyDate(summary.max)}</span>
          </div>
        );
      case "integer":
      case "number":
        // Without a chart
        if (!spec) {
          return (
            <div className="flex flex-col whitespace-pre">
              <span>
                min:{" "}
                {typeof summary.min === "number"
                  ? prettyScientificNumber(summary.min)
                  : summary.min}
              </span>
              <span>
                max:{" "}
                {typeof summary.max === "number"
                  ? prettyScientificNumber(summary.max)
                  : summary.max}
              </span>
              <span>unique: {prettyNumber(summary.unique)}</span>
              <span>nulls: {prettyNumber(summary.nulls)}</span>
            </div>
          );
        }

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
        // Without a chart
        if (!spec) {
          return (
            <div className="flex flex-col whitespace-pre">
              <span>true: {prettyNumber(summary.true)}</span>
              <span>false: {prettyNumber(summary.false)}</span>
            </div>
          );
        }

        if (summary.nulls == null || summary.nulls === 0) {
          return null;
        }

        return (
          <div className="flex flex-col whitespace-pre">
            <span>nulls: {prettyNumber(summary.nulls)}</span>
          </div>
        );
      case "string":
        return (
          <div className="flex flex-col whitespace-pre">
            <span>unique: {prettyNumber(summary.unique)}</span>
            <span>nulls: {prettyNumber(summary.nulls)}</span>
          </div>
        );
      case "unknown":
        return (
          <div className="flex flex-col whitespace-pre">
            <span>nulls: {prettyNumber(summary.nulls)}</span>
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
