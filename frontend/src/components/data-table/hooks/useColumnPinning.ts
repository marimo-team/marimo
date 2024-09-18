/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { SELECT_COLUMN_ID } from "../types";
import type { ColumnPinningState } from "@tanstack/react-table";

interface UseColumnPinningResult {
  columnPinning: ColumnPinningState;
  setColumnPinning: React.Dispatch<React.SetStateAction<ColumnPinningState>>;
}

export function useColumnPinning(
  freezeColumnsLeft?: string[],
  freezeColumnsRight?: string[],
): UseColumnPinningResult {
  const [columnPinning, setColumnPinning] = React.useState<ColumnPinningState>({
    left: maybeAddSelectColumnId(freezeColumnsLeft),
    right: freezeColumnsRight,
  });

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
