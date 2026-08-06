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
const COARSE_MULTIPLIER = 10;
const FINE_MULTIPLIER = 0.1;

/** Step multiplier from modifier keys: shift = coarse, alt = fine. */
const stepMultiplier = (e: { shiftKey: boolean; altKey: boolean }): number => {
  if (e.shiftKey) {
    return COARSE_MULTIPLIER;
  }
  if (e.altKey) {
    return FINE_MULTIPLIER;
  }
  return 1;
};

/** Strip floating-point noise from step arithmetic (e.g. 3 * 0.1). */
const cleanFloat = (x: number): number => Number(x.toPrecision(12));

interface EditState {
  row: number;
  col: number;
  text: string;
  selectAll: boolean;
}

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
    multiplier: number;
  } | null>(null);
  const [activeCell, setActiveCell] = useState<{
    row: number;
    col: number;
  } | null>(null);

  // Draft holds local edits during an active drag/interaction.
  // Outside of a drag we always read from the prop `value` directly,
  // which avoids stale-state bugs when the matrix shape changes.
  const [draft, setDraft] = useState(value);
  useEffect(() => {
    setDraft(value);
  }, [value]);
  const displayValue = activeCell == null ? value : draft;

  // Editing state is mirrored in a ref so that the blur fired while
  // committing (refocusing the cell unmounts the input) can't commit twice.
  const [editing, setEditingState] = useState<EditState | null>(null);
  const editingRef = useRef<EditState | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const setEditing = useCallback((edit: EditState | null) => {
    editingRef.current = edit;
    setEditingState(edit);
  }, []);

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

  const withCellValue = useCallback(
    (base: T, row: number, col: number, newValue: number): T => {
      const copy = base.map((r) => [...r]);
      copy[row][col] = newValue;
      if (symmetric && row !== col) {
        copy[col][row] = newValue;
      }
      return copy;
    },
    [symmetric],
  );

  const startEditing = useCallback(
    (row: number, col: number, seed?: string) => {
      if (disabled[row][col]) {
        return;
      }
      dragState.current = null;
      setActiveCell(null);
      setEditing({
        row,
        col,
        text: seed ?? String(value[row][col]),
        selectAll: seed == null,
      });
    },
    [disabled, value, setEditing],
  );

  // Callback ref: focus the input when it mounts. When editing starts from
  // a typed character, place the caret after the seed instead of selecting.
  const focusInput = useCallback((el: HTMLInputElement | null) => {
    inputRef.current = el;
    if (el) {
      el.focus();
      if (editingRef.current?.selectAll) {
        el.select();
      } else {
        el.setSelectionRange(el.value.length, el.value.length);
      }
    }
  }, []);

  const commitEdit = useCallback(
    (refocusCell: boolean) => {
      const edit = editingRef.current;
      if (!edit) {
        return;
      }
      const cell = refocusCell ? inputRef.current?.closest("td") : null;
      setEditing(null);
      const text = edit.text.trim();
      const parsed = Number(text);
      // Typed values are clamped to bounds but not snapped to `step`,
      // so exact values like 2.32e7 survive.
      if (text !== "" && Number.isFinite(parsed)) {
        const newValue = clampValue(parsed, edit.row, edit.col);
        if (newValue !== value[edit.row][edit.col]) {
          const copy = withCellValue(value, edit.row, edit.col, newValue);
          setDraft(copy);
          setValue(copy);
        }
      }
      cell?.focus();
    },
    [clampValue, value, withCellValue, setValue, setEditing],
  );

  const cancelEdit = useCallback(() => {
    const cell = inputRef.current?.closest("td");
    setEditing(null);
    cell?.focus();
  }, [setEditing]);

  const handleInputKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      e.stopPropagation();
      if (e.key === "Enter") {
        e.preventDefault();
        commitEdit(true);
      } else if (e.key === "Escape") {
        e.preventDefault();
        cancelEdit();
      }
    },
    [commitEdit, cancelEdit],
  );

  const handlePointerDown = useCallback(
    (e: React.PointerEvent, row: number, col: number) => {
      if (
        disabled[row][col] ||
        editing != null ||
        !(e.target instanceof Element)
      ) {
        return;
      }
      e.preventDefault();
      e.target.setPointerCapture(e.pointerId);
      dragState.current = {
        row,
        col,
        startX: e.clientX,
        startValue: displayValue[row][col],
        multiplier: stepMultiplier(e),
      };
      setActiveCell({ row, col });
    },
    [disabled, editing, displayValue],
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      const state = dragState.current;
      if (!state) {
        return;
      }
      const multiplier = stepMultiplier(e);
      if (multiplier !== state.multiplier) {
        // Rebase so toggling a modifier mid-drag rescales future movement
        // instead of jumping the value.
        state.startX = e.clientX;
        state.startValue = displayValue[state.row][state.col];
        state.multiplier = multiplier;
      }
      const { row, col, startX, startValue } = state;
      const dx = e.clientX - startX;
      const cellStep = step[row][col] * multiplier;
      const steps = Math.round(dx / PIXELS_PER_STEP);
      const rawValue = cleanFloat(startValue + steps * cellStep);
      const newValue = clampValue(rawValue, row, col);

      if (newValue !== displayValue[row][col]) {
        const copy = withCellValue(displayValue, row, col, newValue);
        setDraft(copy);
        if (!debounce) {
          setValue(copy);
        }
      }
    },
    [step, clampValue, displayValue, withCellValue, debounce, setValue],
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
      if (disabled[row][col]) {
        return;
      }
      if (e.key === "Enter" || e.key === "F2") {
        e.preventDefault();
        startEditing(row, col);
        return;
      }
      // Typing a number starts editing, seeded with the typed character.
      if (
        e.key.length === 1 &&
        /[\d.+-]/.test(e.key) &&
        !e.ctrlKey &&
        !e.metaKey &&
        !e.altKey
      ) {
        e.preventDefault();
        startEditing(row, col, e.key);
        return;
      }
      const cellStep = step[row][col];
      let delta: number;
      switch (e.key) {
        case "ArrowUp":
          delta = cellStep * stepMultiplier(e);
          break;
        case "ArrowDown":
          delta = -cellStep * stepMultiplier(e);
          break;
        case "PageUp":
          delta = cellStep * COARSE_MULTIPLIER;
          break;
        case "PageDown":
          delta = -cellStep * COARSE_MULTIPLIER;
          break;
        default:
          return;
      }
      e.preventDefault();
      const newValue = clampValue(
        cleanFloat(displayValue[row][col] + delta),
        row,
        col,
      );

      if (newValue !== displayValue[row][col]) {
        const copy = withCellValue(displayValue, row, col, newValue);
        setDraft(copy);
        setValue(copy);
      }
    },
    [
      disabled,
      startEditing,
      step,
      displayValue,
      clampValue,
      withCellValue,
      setValue,
    ],
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
                  const cellEdit =
                    editing != null && editing.row === i && editing.col === j
                      ? editing
                      : null;
                  const rowLabel = rowLabels?.[i] ?? `Row ${i + 1}`;
                  const colLabel = columnLabels?.[j] ?? `Column ${j + 1}`;
                  return (
                    <td
                      key={j}
                      className={cn(
                        "relative text-center min-w-14 h-8 px-2 transition-colors touch-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-hidden",
                        isDisabled
                          ? "cursor-default text-muted-foreground"
                          : cellEdit
                            ? "cursor-text"
                            : "cursor-ew-resize text-link hover:bg-accent",
                        (isActive || cellEdit != null) && "bg-accent",
                        j === 0 && "bracket-l",
                        j === numCols - 1 && "bracket-r",
                        i === 0 && "bracket-t",
                        i === numRows - 1 && "bracket-b",
                      )}
                      tabIndex={isDisabled ? -1 : 0}
                      title={String(cellValue)}
                      aria-label={`${rowLabel}, ${colLabel}`}
                      aria-valuenow={cellValue}
                      aria-valuemin={minValue?.[i]?.[j]}
                      aria-valuemax={maxValue?.[i]?.[j]}
                      aria-disabled={isDisabled || undefined}
                      onPointerDown={(e) => handlePointerDown(e, i, j)}
                      onDoubleClick={() => startEditing(i, j)}
                      onKeyDown={(e) => handleKeyDown(e, i, j)}
                      data-testid={`matrix-cell-${i}-${j}`}
                    >
                      {cellEdit ? (
                        <input
                          ref={focusInput}
                          className="bg-transparent text-center font-mono text-sm text-foreground outline-none select-text"
                          style={{
                            width: `${Math.max(cellEdit.text.length + 2, 6)}ch`,
                          }}
                          value={cellEdit.text}
                          onChange={(e) =>
                            setEditing({ ...cellEdit, text: e.target.value })
                          }
                          onKeyDown={handleInputKeyDown}
                          onBlur={() => commitEdit(false)}
                          onPointerDown={(e) => e.stopPropagation()}
                          aria-label={`Edit ${rowLabel}, ${colLabel}`}
                          data-testid={`matrix-input-${i}-${j}`}
                        />
                      ) : (
                        formatValue(cellValue)
                      )}
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
