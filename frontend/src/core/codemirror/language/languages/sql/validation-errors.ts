/* Copyright 2024 Marimo. All rights reserved. */

import { atom, useAtomValue } from "jotai";
import type { CellId } from "@/core/cells/ids";
import { store } from "@/core/state/jotai";

interface SQLValidationError {
  errorType: string;
  errorMessage: string;
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

export function setSqlValidationError(cellId: CellId, error: string) {
  const sqlValidationErrors = store.get(sqlValidationErrorsAtom);
  const newErrors = new Map(sqlValidationErrors);

  const { errorType, errorMessage } = splitErrorMessage(error);
  newErrors.set(cellId, { errorType, errorMessage });
  store.set(sqlValidationErrorsAtom, newErrors);
}

function splitErrorMessage(error: string) {
  const errorType = error.split(":")[0];
  const errorMessage = error.split(":").slice(1).join(":");
  return { errorType, errorMessage };
}

export const exportedForTesting = {
  splitErrorMessage,
};
