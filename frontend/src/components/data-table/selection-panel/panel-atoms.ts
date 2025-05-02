/* Copyright 2024 Marimo. All rights reserved. */
import { atom } from "jotai";
import type { Row } from "@tanstack/react-table";
import type { CellId } from "@/core/cells/ids";

export const selectionPanelOpenAtom = atom(false);

// Keeps track of the currently focused or selected cell
export const currentlyFocusedCellAtom = atom<CellId>();

// TODO: We can only get rows from current table page
export interface TableData {
  rows: Array<Row<unknown>>;
}

// TODO: We should probably delete old or deleted cells from this atom. Or limit to most recent cells
export const tableDataAtom = atom<Partial<Record<CellId, TableData>>>({});
