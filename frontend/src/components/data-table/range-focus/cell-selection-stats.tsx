/* Copyright 2026 Marimo. All rights reserved. */

import type { Table } from "@tanstack/react-table";
import { useAtomValue } from "jotai";
import { cn } from "@/utils/cn";
import { type SelectedCells, selectedCellsAtom } from "./atoms";
import { getNumericValuesFromSelectedCells } from "./utils";

/**
 * Displays summary stats (Count, Sum, Average) for the current cell selection.
 * Renders only when 2+ cells are selected. Sum and Average are shown only when
 * the selection contains at least one numeric value.
 */
export const CellSelectionStats = <TData,>({
  table,
  className,
}: {
  table: Table<TData>;
  className?: string;
}) => {
  const selectedCells = useAtomValue(selectedCellsAtom);

  if (selectedCells.size < 2) {
    return null;
  }

  return (
    <div
      className={cn(
        "flex items-center justify-end gap-3 px-2 py-1 text-xs text-muted-foreground shrink-0 ml-auto",
        className,
      )}
    >
      <CountStat selectedCells={selectedCells} />
      <SumStat table={table} selectedCells={selectedCells} />
      <AverageStat table={table} selectedCells={selectedCells} />
    </div>
  );
};

const StatSpan = (statName: string, statValue: number) => {
  return (
    <span>
      {statName}: {statValue}
    </span>
  );
};

const CountStat = ({ selectedCells }: { selectedCells: SelectedCells }) => {
  return StatSpan("Count", selectedCells.size);
};

const SumStat = <TData,>({
  table,
  selectedCells,
}: {
  table: Table<TData>;
  selectedCells: SelectedCells;
}) => {
  const numericValues = getNumericValuesFromSelectedCells(table, selectedCells);
  if (numericValues.length === 0) {
    return null;
  }

  const sum = numericValues.reduce((acc, n) => acc + n, 0);
  const sumRounded = Number(sum.toFixed(8));
  return StatSpan("Sum", sumRounded);
};

const AverageStat = <TData,>({
  table,
  selectedCells,
}: {
  table: Table<TData>;
  selectedCells: SelectedCells;
}) => {
  const numericValues = getNumericValuesFromSelectedCells(table, selectedCells);
  if (numericValues.length === 0) {
    return null;
  }

  const average =
    numericValues.reduce((acc, n) => acc + n, 0) / numericValues.length;
  const averageRounded = Number(average.toFixed(8));
  return StatSpan("Average", averageRounded);
};
