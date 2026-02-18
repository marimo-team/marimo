/* Copyright 2026 Marimo. All rights reserved. */
import { type JSX, useCallback, useEffect, useRef, useState } from "react";
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

  // Local display value – always tracks the latest visual state.
  // When debounce is true we update this locally during drag and only
  // call setValue on pointer-up.
  const [internalValue, setInternalValue] = useState(value);
  useEffect(() => {
    setInternalValue(value);
  }, [value]);

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
        startValue: internalValue[row][col],
      };
      setActiveCell({ row, col });
    },
    [disabled, internalValue],
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

      if (newValue !== internalValue[row][col]) {
        const copy = internalValue.map((r) => [...r]);
        copy[row][col] = newValue;
        if (symmetric && row !== col) {
          copy[col][row] = newValue;
        }
        setInternalValue(copy);
        if (!debounce) {
          setValue(copy);
        }
      }
    },
    [step, clampValue, internalValue, symmetric, debounce, setValue],
  );

  const handlePointerUp = useCallback(() => {
    if (debounce && dragState.current) {
      setValue(internalValue);
    }
    dragState.current = null;
    setActiveCell(null);
  }, [debounce, internalValue, setValue]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent, row: number, col: number) => {
      if (e.key === "ArrowUp" || e.key === "ArrowDown") {
        if (disabled[row][col]) {
          return;
        }
        e.preventDefault();
        const cellStep = step[row][col];
        const delta = e.key === "ArrowUp" ? cellStep : -cellStep;
        const newValue = clampValue(internalValue[row][col] + delta, row, col);

        if (newValue !== internalValue[row][col]) {
          const copy = internalValue.map((r) => [...r]);
          copy[row][col] = newValue;
          if (symmetric && row !== col) {
            copy[col][row] = newValue;
          }
          setInternalValue(copy);
          setValue(copy);
        }
      }
    },
    [disabled, step, internalValue, clampValue, symmetric, setValue],
  );

  const hasRowLabels = rowLabels != null && rowLabels.length > 0;
  const hasColumnLabels = columnLabels != null && columnLabels.length > 0;

  return (
    <Labeled label={label} align="top" className="items-center">
      <div
        className="marimo-matrix-bracket relative inline-block px-[14px]"
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
                    className="text-center text-xs font-bold text-muted-foreground px-1 pb-1"
                  >
                    {lbl}
                  </th>
                ))}
              </tr>
            </thead>
          )}
          <tbody>
            {internalValue.map((row, i) => (
              <tr key={i}>
                {hasRowLabels && (
                  <th className="text-right text-xs font-bold text-muted-foreground pr-1.5 h-8">
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
                        "text-right min-w-14 h-8 px-1 rounded transition-colors touch-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                        isDisabled
                          ? "cursor-default text-muted-foreground"
                          : "cursor-ew-resize text-[var(--link)] hover:bg-accent",
                        isActive && "bg-accent",
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
