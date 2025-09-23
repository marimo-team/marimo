/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import type { CellId } from "@/core/cells/ids";
import { store } from "@/core/state/jotai";
import { createReducerAndAtoms } from "@/utils/createReducer";

interface SQLValidationError {
  errorType: string;
  errorMessage: string;
}

interface SQLValidationErrorsState {
  errors: Map<CellId, SQLValidationError>;
}

const initialState = () => ({
  errors: new Map<CellId, SQLValidationError>(),
});

export const {
  reducer,
  valueAtom: sqlValidationErrorsAtom,
  useActions: useSqlValidationErrorsActions,
} = createReducerAndAtoms(initialState, {
  setSqlValidationErrors: (
    state: SQLValidationErrorsState,
    errors: Map<CellId, SQLValidationError>,
  ) => {
    return {
      ...state,
      errors: errors,
    };
  },

  setSqlValidationErrorsForCell: (
    state: SQLValidationErrorsState,
    payload: { cellId: CellId; errors: SQLValidationError },
  ) => {
    return {
      ...state,
      errors: new Map(state.errors).set(payload.cellId, payload.errors),
    };
  },

  addSqlValidationError: (
    state: SQLValidationErrorsState,
    payload: { cellId: CellId; error: SQLValidationError },
  ) => {
    return {
      ...state,
      errors: new Map(state.errors).set(payload.cellId, payload.error),
    };
  },

  clearSqlValidationErrorsForCell: (
    state: SQLValidationErrorsState,
    payload: { cellId: CellId },
  ) => {
    const { cellId } = payload;
    const newMap = new Map(state.errors);
    newMap.delete(cellId);

    return {
      ...state,
      errors: newMap,
    };
  },

  clearSqlValidationErrors: (state: SQLValidationErrorsState) => {
    return {
      ...state,
      errors: new Map<CellId, SQLValidationError>(),
    };
  },
});

export const useSqlValidationErrorsForCell = (cellId: CellId) => {
  const sqlValidationErrors = useAtomValue(sqlValidationErrorsAtom);
  return sqlValidationErrors.errors.get(cellId);
};

/**
 * For cases where we can't use the reducer, call the store directly
 * @param cellId
 */
export function clearSqlValidationError(cellId: CellId) {
  const sqlValidationErrors = store.get(sqlValidationErrorsAtom);
  const newErrors = new Map(sqlValidationErrors.errors);
  newErrors.delete(cellId);
  store.set(sqlValidationErrorsAtom, { errors: newErrors });
}

export function setSqlValidationError(cellId: CellId, error: string) {
  const sqlValidationErrors = store.get(sqlValidationErrorsAtom);
  const newErrors = new Map(sqlValidationErrors.errors);

  const { errorType, errorMessage } = splitErrorMessage(error);
  newErrors.set(cellId, { errorType, errorMessage });
  store.set(sqlValidationErrorsAtom, { errors: newErrors });
}

function splitErrorMessage(error: string) {
  const errorType = error.split(":")[0];
  const errorMessage = error.split(":").slice(1).join(":");
  return { errorType, errorMessage };
}

export const exportedForTesting = {
  reducer,
  useActions: useSqlValidationErrorsActions,
  splitErrorMessage,
};
