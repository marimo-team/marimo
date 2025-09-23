/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-empty-interface */

export interface CellHoverTemplateTableState {
  cellHoverTemplate: string | null;
}

// Use declaration merging to add our new feature APIs
declare module "@tanstack/react-table" {
  interface TableState extends CellHoverTemplateTableState {}
}
