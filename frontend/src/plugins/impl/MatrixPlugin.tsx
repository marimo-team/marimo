/* Copyright 2026 Marimo. All rights reserved. */
import { type JSX, useCallback, useRef, useState } from "react";
import { z } from "zod";
import { cn } from "@/utils/cn";
import type { IPlugin, IPluginProps, Setter } from "../types";
import { Labeled } from "./common/labeled";
import matrixCss from "./matrix.css?inline";

type T = number[][];

interface Data {
  label: string | null;
  minValue?: number[][] | null;
  maxValue?: number[][] | null;
  step: number[][];
  precision: number;
  rowLabels?: string[] | null;
  columnLabels?: string[] | null;
  symmetric: boolean;
  debounce: boolean;
  scientific: boolean;
  disabled: boolean[][];
}

export class MatrixPlugin implements IPlugin<T, Data> {
  tagName = "marimo-matrix";

  cssStyles = [matrixCss];

  validator = z.object({
    initialValue: z.array(z.array(z.number())),
    label: z.string().nullable(),
    minValue: z.array(z.array(z.number())).nullish(),
    maxValue: z.array(z.array(z.number())).nullish(),
    step: z.array(z.array(z.number())),
    precision: z.number(),
    rowLabels: z.array(z.string()).nullish(),
    columnLabels: z.array(z.string()).nullish(),
    symmetric: z.boolean(),
    debounce: z.boolean().default(false),
    scientific: z.boolean(),
    disabled: z.array(z.array(z.boolean())),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return (
      <MatrixComponent
        {...props.data}
        value={props.value}
        setValue={props.setValue}
      />
    );
  }
}

const PIXELS_PER_STEP = 10;

interface MatrixComponentProps extends Data {
  value: T;
  setValue: Setter<T>;
}

const MatrixComponent = ({
  value,
  setValue,
  label,
  minValue,
  maxValue,
  step,
  precision,
  rowLabels,
  columnLabels,
  symmetric,
  debounce,
  scientific,
  disabled,
}: MatrixComponentProps): JSX.Element => {
  const dragState = useRef<{
    row: number;
    col: number;
    startX: number;
    startValue: number;
  } | null>(null);
  const [activeCell, setActiveCell] = useState<{
    row: number;
    col: number;
  } | null>(null);

  // Draft holds local edits during an active drag/interaction.
  // Outside of a drag we always read from the prop `value` directly,
  // which avoids stale-state bugs when the matrix shape changes.
  const [draft, setDraft] = useState(value);
  const displayValue = activeCell == null ? value : draft;

  const formatValue = (val: number) =>
    scientific ? val.toExponential(precision) : val.toFixed(precision);

  const clampValue = useCallback(
    (val: number, row: number, col: number): number => {
      let clamped = val;
      if (minValue != null) {
        clamped = Math.max(clamped, minValue[row][col]);
      }
      if (maxValue != null) {
        clamped = Math.min(clamped, maxValue[row][col]);
      }
      return clamped;
    },
    [minValue, maxValue],
  );

  const handlePointerDown = useCallback(
    (e: React.PointerEvent, row: number, col: number) => {
      if (disabled[row][col] || !(e.target instanceof Element)) {
        return;
      }
      e.preventDefault();
      e.target.setPointerCapture(e.pointerId);
      dragState.current = {
        row,
        col,
        startX: e.clientX,
        startValue: displayValue[row][col],
      };
      setActiveCell({ row, col });
    },
    [disabled, displayValue],
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      const state = dragState.current;
      if (!state) {
        return;
      }
      const { row, col, startX, startValue } = state;
      const dx = e.clientX - startX;
      const cellStep = step[row][col];
      const steps = Math.round(dx / PIXELS_PER_STEP);
      const rawValue = startValue + steps * cellStep;
      const newValue = clampValue(rawValue, row, col);

      if (newValue !== displayValue[row][col]) {
        const copy = displayValue.map((r) => [...r]);
        copy[row][col] = newValue;
        if (symmetric && row !== col) {
          copy[col][row] = newValue;
        }
        setDraft(copy);
        if (!debounce) {
          setValue(copy);
        }
      }
    },
    [step, clampValue, displayValue, symmetric, debounce, setValue],
  );

  const handlePointerUp = useCallback(() => {
    if (debounce && dragState.current) {
      setValue(displayValue);
    }
    dragState.current = null;
    setActiveCell(null);
  }, [debounce, displayValue, setValue]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent, row: number, col: number) => {
      if (e.key === "ArrowUp" || e.key === "ArrowDown") {
        if (disabled[row][col]) {
          return;
        }
        e.preventDefault();
        const cellStep = step[row][col];
        const delta = e.key === "ArrowUp" ? cellStep : -cellStep;
        const newValue = clampValue(displayValue[row][col] + delta, row, col);

        if (newValue !== displayValue[row][col]) {
          const copy = displayValue.map((r) => [...r]);
          copy[row][col] = newValue;
          if (symmetric && row !== col) {
            copy[col][row] = newValue;
          }
          setDraft(copy);
          setValue(copy);
        }
      }
    },
    [disabled, step, displayValue, clampValue, symmetric, setValue],
  );

  const hasRowLabels = rowLabels != null && rowLabels.length > 0;
  const hasColumnLabels = columnLabels != null && columnLabels.length > 0;

  const numRows = displayValue.length;
  const numCols = displayValue[0]?.length ?? 0;

  return (
    <Labeled label={label} align="top" className="items-center">
      <div
        className="relative inline-block"
        data-testid="marimo-plugin-matrix"
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        <table
          className="font-mono text-sm tabular-nums select-none border-separate border-spacing-0"
          role="group"
          aria-label={label || "Matrix"}
        >
          {hasColumnLabels && (
            <thead>
              <tr>
                {hasRowLabels && <th />}
                {columnLabels.map((lbl, j) => (
                  <th
                    key={j}
                    className="text-center text-sm font-medium text-foreground px-2 pb-1"
                  >
                    {lbl}
                  </th>
                ))}
              </tr>
            </thead>
          )}
          <tbody>
            {displayValue.map((row, i) => (
              <tr key={i}>
                {hasRowLabels && (
                  <th className="text-right text-sm font-medium text-foreground pr-3 h-8">
                    {rowLabels[i]}
                  </th>
                )}
                {row.map((cellValue, j) => {
                  const isDisabled = disabled[i][j];
                  const isActive =
                    activeCell?.row === i && activeCell?.col === j;
                  const rowLabel = rowLabels?.[i] ?? `Row ${i + 1}`;
                  const colLabel = columnLabels?.[j] ?? `Column ${j + 1}`;
                  return (
                    <td
                      key={j}
                      className={cn(
                        "relative text-center min-w-14 h-8 px-2 transition-colors touch-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                        isDisabled
                          ? "cursor-default text-muted-foreground"
                          : "cursor-ew-resize text-[var(--link)] hover:bg-accent",
                        isActive && "bg-accent",
                        j === 0 && "bracket-l",
                        j === numCols - 1 && "bracket-r",
                        i === 0 && "bracket-t",
                        i === numRows - 1 && "bracket-b",
                      )}
                      tabIndex={isDisabled ? -1 : 0}
                      aria-label={`${rowLabel}, ${colLabel}`}
                      aria-valuenow={cellValue}
                      aria-valuemin={minValue?.[i]?.[j]}
                      aria-valuemax={maxValue?.[i]?.[j]}
                      aria-disabled={isDisabled || undefined}
                      onPointerDown={(e) => handlePointerDown(e, i, j)}
                      onKeyDown={(e) => handleKeyDown(e, i, j)}
                      data-testid={`matrix-cell-${i}-${j}`}
                    >
                      {formatValue(cellValue)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Labeled>
  );
};
