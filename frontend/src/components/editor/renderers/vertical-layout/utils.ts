/* Copyright 2026 Marimo. All rights reserved. */

import { isOutputEmpty } from "@/core/cells/outputs";
import type { CellData, CellRuntimeState } from "@/core/cells/types";
import { MarkdownLanguageAdapter } from "@/core/codemirror/language/languages/markdown";
import { KnownQueryParams } from "@/core/constants";
import type { OutputMessage } from "@/core/kernel/messages";
import { isStaticNotebook } from "@/core/static/static-state";
import { isWasm } from "@/core/wasm/utils";
import { updateQueryParams } from "@/utils/urls";

export function getInitialShowCode({
  showCodeInRunModePreference,
  kioskMode,
}: {
  showCodeInRunModePreference: boolean;
  kioskMode: boolean;
}): boolean {
  // The mount option takes precedence over other defaults.
  if (!showCodeInRunModePreference) {
    return false;
  }

  const showCodeByQueryParam = new URLSearchParams(window.location.search).get(
    KnownQueryParams.showCode,
  );

  // Static notebooks, WASM notebooks, and kiosk mode show code by default.
  return showCodeByQueryParam === null
    ? isStaticNotebook() || isWasm() || kioskMode
    : showCodeByQueryParam === "true";
}

export function updateShowCodeQueryParam(showCode: boolean): void {
  // Persist explicit user choices in shareable static notebook URLs. Avoid
  // adding the parameter on startup so unchanged URLs retain their defaults.
  if (isStaticNotebook()) {
    updateQueryParams((params) => {
      params.set(KnownQueryParams.showCode, String(showCode));
    });
  }
}

export function groupCellsByColumn(
  cells: (CellRuntimeState & CellData)[],
): [number, (CellRuntimeState & CellData)[]][] {
  // Group cells by column
  const cellsByColumn = new Map<number, (CellRuntimeState & CellData)[]>();
  let lastSeenColumn = 0;
  cells.forEach((cell) => {
    const column = cell.config.column ?? lastSeenColumn;
    lastSeenColumn = column;
    if (!cellsByColumn.has(column)) {
      cellsByColumn.set(column, []);
    }
    cellsByColumn.get(column)?.push(cell);
  });

  // Sort columns by index
  return [...cellsByColumn.entries()].toSorted(([a], [b]) => a - b);
}

/**
 * Determine if the code should be hidden.
 *
 * This is used to hide the code if it's pure markdown and there's an output,
 * or if the code is empty.
 */
export function shouldHideCode(code: string, output: OutputMessage | null) {
  const isPureMarkdown = new MarkdownLanguageAdapter().isSupported(code);
  const hasOutput = output !== null && !isOutputEmpty(output);
  return (isPureMarkdown && hasOutput) || code.trim() === "";
}
