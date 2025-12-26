/* Copyright 2026 Marimo. All rights reserved. */

import type { CompletionSection } from "@codemirror/autocomplete";

/** Number from -99 to 99. Higher numbers are prioritized when surfacing completions. */
export const Boosts = {
  LOCAL_TABLE: 7,
  REMOTE_TABLE: 5,
  HIGH: 4,
  MEDIUM: 3,
  CELL_OUTPUT: 2,
  LOW: 2,
} as const;

export const Sections = {
  ERROR: { name: "Error", rank: 1 },
  TABLE: { name: "Table", rank: 2 },
  DATA_SOURCES: { name: "Data Sources", rank: 3 },
  VARIABLE: { name: "Variable", rank: 4 },
  CELL_OUTPUT: { name: "Cell Output", rank: 5 },
  FILE: { name: "File", rank: 6 },
} satisfies Record<string, CompletionSection>;
