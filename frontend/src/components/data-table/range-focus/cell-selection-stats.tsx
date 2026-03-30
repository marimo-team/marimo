/* Copyright 2026 Marimo. All rights reserved. */

import type { Table } from "@tanstack/react-table";
import { useAtomValue } from "jotai";
import { useLocale } from "react-aria";
import { cn } from "@/utils/cn";
import { selectedCellsAtom } from "./atoms";
import {
  countDataCellsInSelection,
  getNumericValuesFromSelectedCells,
} from "./utils";

// Offers a good default for most use cases.
const MAX_FRACTION_DIGITS = 3;

/**
 * Displays summary stats (Count, Sum, Average) for the current cell selection.
 * Renders only when 2+ data cells are selected (checkbox column excluded).
 * Count excludes the checkbox column; Sum and Average are shown only when
 * the selection contains at least one numeric value.
 */
export const CellSelectionStats = <TData,>({
  table,
  className,
}: {
  table: Table<TData>;
  className?: string;
}) => {
  const { locale } = useLocale();
  const selectedCells = useAtomValue(selectedCellsAtom);
  const dataCellCount = countDataCellsInSelection(selectedCells);

  if (dataCellCount < 2) {
    return (
      <span className={cn("text-xs text-muted-foreground italic", className)}>
        Select multiple cells to see stats
      </span>
    );
  }

  const numericValues = getNumericValuesFromSelectedCells(table, selectedCells);

  return (
    <div
      className={cn(
        "flex items-center justify-end gap-3 text-xs text-muted-foreground shrink-0",
        className,
      )}
    >
      <CountStat count={dataCellCount} locale={locale} />
      <SumStat numericValues={numericValues} locale={locale} />
      <AverageStat numericValues={numericValues} locale={locale} />
    </div>
  );
};

const formatNumber = (value: number, locale: string): string => {
  return value.toLocaleString(locale, {
    maximumFractionDigits: MAX_FRACTION_DIGITS,
  });
};

const StatSpan = ({
  name,
  value,
  locale,
}: {
  name: string;
  value: number;
  locale: string;
}) => {
  return (
    <span>
      {name}: {formatNumber(value, locale)}
    </span>
  );
};

const CountStat = ({ count, locale }: { count: number; locale: string }) => {
  return <StatSpan name="Count" value={count} locale={locale} />;
};

const SumStat = ({
  numericValues,
  locale,
}: {
  numericValues: number[];
  locale: string;
}) => {
  if (numericValues.length === 0) {
    return null;
  }

  const sum = numericValues.reduce((acc, n) => acc + n, 0);
  const sumRounded = Number(sum.toFixed(MAX_FRACTION_DIGITS));
  return <StatSpan name="Sum" value={sumRounded} locale={locale} />;
};

const AverageStat = ({
  numericValues,
  locale,
}: {
  numericValues: number[];
  locale: string;
}) => {
  if (numericValues.length === 0) {
    return null;
  }

  const average =
    numericValues.reduce((acc, n) => acc + n, 0) / numericValues.length;
  const averageRounded = Number(average.toFixed(MAX_FRACTION_DIGITS));
  return <StatSpan name="Average" value={averageRounded} locale={locale} />;
};
