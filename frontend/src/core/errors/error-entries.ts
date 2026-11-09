/* Copyright 2026 Marimo. All rights reserved. */

import { notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { displayCellName } from "@/core/cells/names";
import {
  type CellError,
  type CellOutput,
  cellOutputAtom,
} from "@/core/executions";
import type { OutputMessage } from "@/core/kernel/messages";
import { isErrorMime, isMarimoErrorsMime, isTracebackMime } from "@/core/mime";
import type { JotaiStore } from "@/core/state/jotai";
import { logNever } from "@/utils/assertNever";
import { parseHtmlContent } from "@/utils/dom";

export interface CellErrorEntry {
  cellId: CellId;
  cellName: string;
  cellCode: string;
  errorData: CellError[];
  tracebackHtml?: string;
}

function parseCellErrorOutput(
  output: CellOutput,
): Pick<CellErrorEntry, "errorData" | "tracebackHtml"> | null {
  if (isMarimoErrorsMime(output.mimetype)) {
    if (!Array.isArray(output.data)) {
      return null;
    }
    const errorData = output.data.filter(
      (error) => !error.type.includes("ancestor"),
    );
    if (errorData.length === 0) {
      return null;
    }
    return { errorData };
  }

  if (isTracebackMime(output.mimetype)) {
    if (typeof output.data !== "string" || output.data.length === 0) {
      return null;
    }
    return { errorData: [], tracebackHtml: output.data };
  }

  return null;
}

function errorDataHasTraceback(errorData: readonly CellError[]): boolean {
  return errorData.some((error) => "traceback" in error && error.traceback);
}

function getTracebackFromConsole(
  consoleOutputs: OutputMessage[] | undefined,
): string | undefined {
  const tracebackOutput = consoleOutputs?.find((output) =>
    isTracebackMime(output.mimetype),
  );
  if (
    !tracebackOutput ||
    typeof tracebackOutput.data !== "string" ||
    tracebackOutput.data.length === 0
  ) {
    return undefined;
  }
  return tracebackOutput.data;
}

function resolveTracebackHtml(
  parsed: Pick<CellErrorEntry, "errorData" | "tracebackHtml">,
  consoleOutputs: OutputMessage[] | undefined,
): string | undefined {
  if (parsed.tracebackHtml) {
    return parsed.tracebackHtml;
  }
  if (errorDataHasTraceback(parsed.errorData)) {
    return undefined;
  }
  return getTracebackFromConsole(consoleOutputs);
}

export function getCellErrorEntries(store: JotaiStore): CellErrorEntry[] {
  const { cellIds, cellRuntime, cellData } = store.get(notebookAtom);
  const entries: CellErrorEntry[] = [];

  for (const [cellIndex, cellId] of cellIds.entries()) {
    const output = store.get(cellOutputAtom(cellId));
    if (output === null || !isErrorMime(output.mimetype)) {
      continue;
    }

    const parsed = parseCellErrorOutput(output);
    if (!parsed) {
      continue;
    }

    const cellName = displayCellName(cellData[cellId].name, cellIndex);
    // The source that raised, while the host still has it.
    const cellCode = output.code ?? cellData[cellId].code;

    entries.push({
      cellId,
      cellName,
      cellCode,
      errorData: parsed.errorData,
      tracebackHtml: resolveTracebackHtml(
        parsed,
        cellRuntime[cellId].consoleOutputs,
      ),
    });
  }

  return entries;
}

export function describeError(error: CellError): string {
  if (error.type === "diagnostic") {
    return error.msg;
  }
  if (error.type === "setup-refs") {
    return "The setup cell cannot have references";
  }
  if (error.type === "cycle") {
    return "This cell is in a cycle";
  }
  if (error.type === "multiple-defs") {
    return `The variable '${error.name}' was defined by another cell`;
  }
  if (error.type === "import-star") {
    return error.msg;
  }
  if (error.type === "lazy-import") {
    return error.msg;
  }
  if (error.type === "ancestor-stopped") {
    return error.msg;
  }
  if (error.type === "ancestor-prevented") {
    return error.msg;
  }
  if (error.type === "exception") {
    return error.msg;
  }
  if (error.type === "strict-exception") {
    return error.msg;
  }
  if (error.type === "interruption") {
    return "This cell was interrupted and needs to be re-run";
  }
  if (error.type === "syntax") {
    return error.msg;
  }
  if (error.type === "unknown") {
    return error.msg;
  }
  if (error.type === "sql-error") {
    return error.msg;
  }
  if (error.type === "internal") {
    return error.msg || "An internal error occurred";
  }
  logNever(error);
  return "Unknown error";
}

export function formatSingleError(error: CellError): string {
  let text = describeError(error);
  if ("traceback" in error && error.traceback) {
    text += `\n\nTraceback:\n${parseHtmlContent(error.traceback)}`;
  }
  return text;
}

export function formatCellError(entry: CellErrorEntry): string {
  const parts = [entry.cellName];

  if (entry.tracebackHtml) {
    parts.push(parseHtmlContent(entry.tracebackHtml));
  }

  if (entry.errorData.length > 0) {
    parts.push(entry.errorData.map(formatSingleError).join("\n\n"));
  }

  return parts.join("\n\n");
}
