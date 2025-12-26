/* Copyright 2026 Marimo. All rights reserved. */

import type { SupportedDialects } from "@marimo-team/codemirror-sql";
import { atom, useAtomValue } from "jotai";
import type { CellId } from "@/core/cells/ids";
import { store } from "@/core/state/jotai";

export interface SQLValidationError {
  errorType: string;
  errorMessage: string;
  codeblock?: string; // Code block that caused the error
}

type CellToSQLErrors = Map<CellId, SQLValidationError>;

export const sqlValidationErrorsAtom = atom<CellToSQLErrors>(
  new Map<CellId, SQLValidationError>(),
);

export const useSqlValidationErrorsForCell = (cellId: CellId) => {
  const sqlValidationErrors = useAtomValue(sqlValidationErrorsAtom);
  return sqlValidationErrors.get(cellId);
};

export function clearSqlValidationError(cellId: CellId) {
  const sqlValidationErrors = store.get(sqlValidationErrorsAtom);
  const newErrors = new Map(sqlValidationErrors);
  newErrors.delete(cellId);
  store.set(sqlValidationErrorsAtom, newErrors);
}

export function clearAllSqlValidationErrors() {
  store.set(sqlValidationErrorsAtom, new Map<CellId, SQLValidationError>());
}

export function setSqlValidationError({
  cellId,
  errorMessage,
  dialect,
}: {
  cellId: CellId;
  errorMessage: string;
  dialect: SupportedDialects | null;
}) {
  const sqlValidationErrors = store.get(sqlValidationErrorsAtom);
  const newErrors = new Map(sqlValidationErrors);

  const errorResult: SQLValidationError =
    dialect === "DuckDB"
      ? handleDuckdbError(errorMessage)
      : splitErrorMessage(errorMessage);

  newErrors.set(cellId, errorResult);
  store.set(sqlValidationErrorsAtom, newErrors);
}

function handleDuckdbError(error: string): SQLValidationError {
  const { errorType, errorMessage } = splitErrorMessage(error);
  let newErrorMessage = errorMessage;

  // Extract the LINE and the rest of the message as codeblock, keep errorMessage as whatever is before
  let codeblock: string | undefined;
  const lineIndex = errorMessage.indexOf("LINE ");
  if (lineIndex !== -1) {
    codeblock = errorMessage.slice(Math.max(0, lineIndex)).trim();
    newErrorMessage = errorMessage.slice(0, Math.max(0, lineIndex)).trim();
  }

  return {
    errorType,
    errorMessage: newErrorMessage,
    codeblock,
  };
}

function splitErrorMessage(error: string) {
  const errorType = error.split(":")[0].trim();
  const errorMessage = error.split(":").slice(1).join(":").trim();
  return { errorType, errorMessage };
}

export const exportedForTesting = {
  splitErrorMessage,
  handleDuckdbError,
};
