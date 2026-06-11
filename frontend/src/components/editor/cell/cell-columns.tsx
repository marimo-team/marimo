/* Copyright 2026 Marimo. All rights reserved. */
import type React from "react";
import { useRef } from "react";
import { cn } from "@/utils/cn";
import { Logger } from "@/utils/Logger";
import type { CellOutputPosition } from "../renderers/types";

/**
 * Side-by-side cell layout: the code editor and the cell output sit in two
 * columns inside the cell card, separated by a draggable resizer.
 *
 * The editor's share of the row is held in a single CSS custom property on the
 * document root, shared by every cell. This keeps the value out of React state,
 * so dragging the resizer re-renders nothing — all cells stay in sync by
 * reading the same variable — and the chosen split is persisted to localStorage
 * so it survives reloads.
 */

const SPLIT_VAR = "--marimo-cell-columns-split";
const STORAGE_KEY = "marimo:cell-columns:split";
const DEFAULT_SPLIT = 0.5;
const MIN_SPLIT = 0.2;
const MAX_SPLIT = 0.8;

const clampSplit = (value: number): number =>
  Math.min(MAX_SPLIT, Math.max(MIN_SPLIT, value));

const applySplit = (fraction: number): void => {
  document.documentElement.style.setProperty(SPLIT_VAR, `${fraction * 100}%`);
};

const readSplit = (): number => {
  const percent = Number.parseFloat(
    document.documentElement.style.getPropertyValue(SPLIT_VAR),
  );
  return Number.isFinite(percent) ? clampSplit(percent / 100) : DEFAULT_SPLIT;
};

const persistSplit = (fraction: number): void => {
  try {
    window.localStorage.setItem(STORAGE_KEY, String(fraction));
  } catch (error) {
    Logger.warn("Failed to persist cell column split", error);
  }
};

const loadStoredSplit = (): number => {
  try {
    const fraction = Number.parseFloat(
      window.localStorage.getItem(STORAGE_KEY) ?? "",
    );
    return Number.isFinite(fraction) ? clampSplit(fraction) : DEFAULT_SPLIT;
  } catch {
    return DEFAULT_SPLIT;
  }
};

// Seed the shared split from localStorage before the first cell paints so
// columns don't flash from the default width to the stored width.
if (typeof document !== "undefined") {
  applySplit(loadStoredSplit());
}

const ColumnResizer: React.FC = () => {
  const ref = useRef<HTMLDivElement>(null);

  // Compute the editor's fraction of the row from a pointer position,
  // accounting for the reversed (output-on-left) layout.
  const fractionFromPointer = (row: HTMLElement, clientX: number): number => {
    const rect = row.getBoundingClientRect();
    if (rect.width === 0) {
      return readSplit();
    }
    const reversed = row.classList.contains("cell-columns--reverse");
    const editorWidth = reversed ? rect.right - clientX : clientX - rect.left;
    return clampSplit(editorWidth / rect.width);
  };

  const onPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    const handle = ref.current;
    const row = handle?.closest<HTMLElement>(".cell-columns");
    if (!handle || !row) {
      return;
    }
    event.preventDefault();
    handle.setPointerCapture(event.pointerId);

    const onMove = (e: PointerEvent) =>
      applySplit(fractionFromPointer(row, e.clientX));

    const onUp = () => {
      handle.removeEventListener("pointermove", onMove);
      handle.removeEventListener("pointerup", onUp);
      persistSplit(readSplit());
    };

    handle.addEventListener("pointermove", onMove);
    handle.addEventListener("pointerup", onUp);
  };

  return (
    <div
      ref={ref}
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize code and output columns"
      tabIndex={0}
      className="cell-columns__resizer"
      onPointerDown={onPointerDown}
    />
  );
};

interface CellColumnsProps {
  outputPosition: Extract<CellOutputPosition, "left" | "right">;
  codeEditor: React.ReactNode;
  /** The cell output. Falsy when the cell has produced no output yet. */
  output: React.ReactNode;
  /** Cell-level chrome (drag handle, delete) anchored to the whole row. */
  children?: React.ReactNode;
}

/**
 * Renders a cell's editor and output as two columns. When there is no output,
 * the editor fills the row and no resizer is shown.
 */
export const CellColumns: React.FC<CellColumnsProps> = ({
  outputPosition,
  codeEditor,
  output,
  children,
}) => {
  const hasOutput = Boolean(output);
  return (
    <div
      className={cn(
        "cell-columns",
        outputPosition === "left" && "cell-columns--reverse",
        hasOutput && "cell-columns--resizable",
      )}
    >
      {codeEditor}
      {hasOutput && <ColumnResizer />}
      {output}
      {children}
    </div>
  );
};
