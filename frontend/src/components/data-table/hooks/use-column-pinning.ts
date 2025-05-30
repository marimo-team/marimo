/* Copyright 2024 Marimo. All rights reserved. */
"use no memo";

import React from "react";
import { SELECT_COLUMN_ID } from "../types";
import type { ColumnPinningState } from "@tanstack/react-table";
import { useInternalStateWithSync } from "@/hooks/useInternalStateWithSync";
import { isEqual } from "lodash-es";

interface UseColumnPinningResult {
  columnPinning: ColumnPinningState;
  setColumnPinning: React.Dispatch<React.SetStateAction<ColumnPinningState>>;
}

export function useColumnPinning(
  freezeColumnsLeft?: string[],
  freezeColumnsRight?: string[],
): UseColumnPinningResult {
  const [columnPinning, setColumnPinning] =
    useInternalStateWithSync<ColumnPinningState>(
      {
        left: maybeAddSelectColumnId(freezeColumnsLeft),
        right: freezeColumnsRight,
      },
      isEqual,
    );

  const setColumnPinningWithFreeze = (
    newState: React.SetStateAction<ColumnPinningState>,
  ) => {
    setColumnPinning((prevState) => {
      const updatedState =
        typeof newState === "function" ? newState(prevState) : newState;
      return {
        left: maybeAddSelectColumnId(updatedState.left),
        right: updatedState.right,
      };
    });
  };

  return { columnPinning, setColumnPinning: setColumnPinningWithFreeze };
}

function maybeAddSelectColumnId(freezeColumns: string[] | undefined): string[] {
  if (!freezeColumns || freezeColumns.length === 0) {
    return [];
  }
  return freezeColumns.includes(SELECT_COLUMN_ID)
    ? freezeColumns
    : [SELECT_COLUMN_ID, ...freezeColumns];
}
