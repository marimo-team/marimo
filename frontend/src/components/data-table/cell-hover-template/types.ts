/* Copyright 2026 Marimo. All rights reserved. */
/* oxlint-disable typescript/no-empty-object-type */

export interface CellHoverTemplateTableState {
  cellHoverTemplate: string | null;
}

// Use declaration merging to add our new feature APIs
declare module "@tanstack/react-table" {
  interface TableState extends CellHoverTemplateTableState {}
}
