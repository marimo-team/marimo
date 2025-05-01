/* Copyright 2024 Marimo. All rights reserved. */
import { atom } from "jotai";
import type { TableState } from "@tanstack/react-table";
import type { CellId } from "@/core/cells/ids";

export const selectionPanelOpenAtom = atom(false);

// Keeps track of the currently focused or selected cell
export const currentlyFocusedCellAtom = atom<CellId>();

export const tableDataAtom = atom<Record<CellId, TableState>>();
