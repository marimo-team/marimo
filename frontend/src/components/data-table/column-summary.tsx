/* Copyright 2024 Marimo. All rights reserved. */
import React, { useContext } from "react";
import { ColumnChartSpecModel } from "./chart-spec-model";
import { useTheme } from "@/theme/useTheme";
import { prettyNumber, prettyScientificNumber } from "@/utils/numbers";
import { prettyDate } from "@/utils/dates";
import { DelayMount } from "../utils/delay-mount";
import { ChartSkeleton } from "../charts/chart-skeleton";
import { logNever } from "@/utils/assertNever";
import { DatePopover } from "./date-popover";
import { createBatchedLoader } from "@/plugins/impl/vega/batched";

export const ColumnChartContext = React.createContext<
  ColumnChartSpecModel<unknown>
>(ColumnChartSpecModel.EMPTY);

interface Props<TData, TValue> {
  columnId: string;
}

const LazyVegaLite = React.lazy(() =>
  import("react-vega").then((m) => ({ default: m.VegaLite })),
);

// We batch multiple calls to the same URL returning the same promise
// for all calls with the same key.
const batchedLoader = createBatchedLoader();

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
        visibility={true}
        rootMargin="200px"
        fallback={<ChartSkeleton seed={columnId} width={80} height={40} />}
      >
        <LazyVegaLite
          spec={spec}
          width={70}
          height={30}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          loader={batchedLoader as any}
          style={{ minWidth: "unset", maxHeight: "40px" }}
          actions={false}
          theme={theme === "dark" ? "dark" : "vox"}
        />
      </DelayMount>
    );
  }

  const renderDate = (
    date: string | number | null | undefined,
    type: "date" | "datetime",
  ) => {
    return (
      <DatePopover date={date} type={type}>
        {prettyDate(date, type)}
      </DatePopover>
    );
  };

  const renderStats = () => {
    if (!summary) {
      return null;
    }

    switch (type) {
      case "date":
      case "datetime":
        // Without a chart
        if (!spec) {
          return (
            <div className="flex flex-col whitespace-pre">
              <span>min: {renderDate(summary.min, type)}</span>
              <span>max: {renderDate(summary.max, type)}</span>
              <span>unique: {prettyNumber(summary.unique)}</span>
              <span>nulls: {prettyNumber(summary.nulls)}</span>
            </div>
          );
        }

        return (
          <div className="flex justify-between w-full px-2 whitespace-pre">
            <span>{renderDate(summary.min, type)}</span>
            {summary.min === summary.max
              ? null
              : -(<span>{renderDate(summary.max, type)}</span>)}
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
              {summary.min === summary.max ? null : (
                <span>{prettyScientificNumber(summary.max)}</span>
              )}
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
      case "time":
        return null;
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
      default:
        logNever(type);
        return null;
    }
  };

  return (
    <div className="flex flex-col items-center text-xs text-muted-foreground align-end">
      {chart}
      {renderStats()}
    </div>
  );
};
