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
    left: freezeColumnsLeft
      ? [SELECT_COLUMN_ID, ...freezeColumnsLeft]
      : [SELECT_COLUMN_ID],
    right: freezeColumnsRight,
  });

  const setColumnPinningWithFreeze = React.useCallback(
    (newState: React.SetStateAction<ColumnPinningState>) => {
      setColumnPinning((prevState) => {
        const updatedState =
          typeof newState === "function" ? newState(prevState) : newState;
        return {
          left:
            !freezeColumnsLeft || freezeColumnsLeft?.includes(SELECT_COLUMN_ID)
              ? freezeColumnsLeft
              : [SELECT_COLUMN_ID, ...(freezeColumnsLeft || [])],
          right: freezeColumnsRight,
          ...updatedState,
        };
      });
    },
    [freezeColumnsLeft, freezeColumnsRight],
  );

  return { columnPinning, setColumnPinning: setColumnPinningWithFreeze };
}
