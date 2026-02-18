/* Copyright 2026 Marimo. All rights reserved. */
import { type JSX, useCallback, useRef, useState } from "react";
import { z } from "zod";
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
      if (disabled[row][col]) {
        return;
      }
      e.preventDefault();
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
      dragState.current = {
        row,
        col,
        startX: e.clientX,
        startValue: value[row][col],
      };
      setActiveCell({ row, col });
    },
    [disabled, value],
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

      if (newValue !== value[row][col]) {
        const copy = value.map((r) => [...r]);
        copy[row][col] = newValue;
        if (symmetric && row !== col) {
          copy[col][row] = newValue;
        }
        setValue(copy);
      }
    },
    [step, clampValue, value, symmetric, setValue],
  );

  const handlePointerUp = useCallback(() => {
    dragState.current = null;
    setActiveCell(null);
  }, []);

  const hasRowLabels = rowLabels != null && rowLabels.length > 0;
  const hasColumnLabels = columnLabels != null && columnLabels.length > 0;

  return (
    <Labeled label={label} align="top" className="items-center">
      <div
        className="marimo-matrix-container"
        data-testid="marimo-plugin-matrix"
      >
        {hasColumnLabels && (
          <div className="marimo-matrix-column-labels">
            {hasRowLabels && <div className="marimo-matrix-row-label" />}
            <div style={{ padding: "0 8px", display: "flex", gap: 0 }}>
              {columnLabels.map((lbl, j) => (
                <div key={j} className="marimo-matrix-column-label">
                  {lbl}
                </div>
              ))}
            </div>
          </div>
        )}
        <div className="marimo-matrix-body">
          {hasRowLabels && (
            <div className="marimo-matrix-row-labels">
              {rowLabels.map((lbl, i) => (
                <div key={i} className="marimo-matrix-row-label">
                  {lbl}
                </div>
              ))}
            </div>
          )}
          <div className="marimo-matrix-bracket">
            {value.map((row, i) => (
              <div key={i} className="marimo-matrix-row">
                {row.map((cellValue, j) => {
                  const isDisabled = disabled[i][j];
                  const isActive =
                    activeCell?.row === i && activeCell?.col === j;
                  return (
                    <div
                      key={j}
                      className={`marimo-matrix-cell${isDisabled ? " disabled" : ""}${isActive ? " active" : ""}`}
                      onPointerDown={(e) => handlePointerDown(e, i, j)}
                      onPointerMove={handlePointerMove}
                      onPointerUp={handlePointerUp}
                      data-testid={`matrix-cell-${i}-${j}`}
                    >
                      {scientific
                        ? cellValue.toExponential(precision)
                        : cellValue.toFixed(precision)}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>
    </Labeled>
  );
};
