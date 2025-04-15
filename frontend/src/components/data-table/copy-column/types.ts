/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-empty-interface */
import type { RowData } from "@tanstack/react-table";

export interface CopyColumnOptions {
  enableCopyColumn?: boolean;
}

export interface CopyColumnInstance {
  getCanCopy?: () => boolean;
}

// Use declaration merging to add our new feature APIs
declare module "@tanstack/react-table" {
  interface TableOptionsResolved<TData extends RowData>
    extends CopyColumnOptions {}

  interface Column<TData extends RowData> extends CopyColumnInstance {}
}
