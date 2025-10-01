/* Copyright 2024 Marimo. All rights reserved. */

/** Number from -99 to 99. Higher numbers are prioritized when surfacing completions. */
export const Boosts = {
  LOCAL_TABLE: 5,
  REMOTE_TABLE: 4,
  HIGH: 4,
  VARIABLE: 3,
  MEDIUM: 3,
  CELL_OUTPUT: 2,
  LOW: 2,
  ERROR: 1,
} as const;
