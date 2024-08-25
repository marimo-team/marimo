/* Copyright 2024 Marimo. All rights reserved. */
export type ColumnPinningPosition = false | "left" | "right";

export interface ColumnPinningState {
  left?: string[];
  right?: string[];
}

export interface ColumnPinningTableState {
  columnPinning: ColumnPinningState;
}
