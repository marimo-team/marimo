/* Copyright 2024 Marimo. All rights reserved. */

import { atom } from "jotai";

export interface SelectedCell {
  rowId: string;
  columnId: string;
  cellId: string; // unique id for the cell
}

export type SelectedCells = Set<string>;

// Core selection state atoms
export const selectedCellsAtom = atom<SelectedCells>(new Set<string>());
export const copiedCellsAtom = atom<SelectedCells>(new Set<string>());
export const selectedStartCellAtom = atom<SelectedCell | null>(null);
export const focusedCellAtom = atom<SelectedCell | null>(null);
export const isSelectingAtom = atom<boolean>(false);

// Action atoms
export const clearSelectionAtom = atom(null, (get, set) => {
  set(selectedCellsAtom, new Set());
  set(selectedStartCellAtom, null);
  set(focusedCellAtom, null);
});

export const setCopiedCellsAtom = atom(
  null,
  (get, set, cellIds: SelectedCells) => {
    set(copiedCellsAtom, cellIds);
    // Auto-clear after 500ms
    setTimeout(() => {
      set(copiedCellsAtom, new Set());
    }, 500);
  },
);

// Optimized derived atoms for individual cell state
// These create focused atoms that only update when a specific cell's state changes
export const createCellSelectedAtom = (cellId: string) =>
  atom((get) => {
    const selectedCells = get(selectedCellsAtom);
    return selectedCells.has(cellId);
  });

export const createCellCopiedAtom = (cellId: string) =>
  atom((get) => {
    const copiedCells = get(copiedCellsAtom);
    return copiedCells.has(cellId);
  });

export const createCellStateAtom = (cellId: string) =>
  atom((get) => {
    const selectedCells = get(selectedCellsAtom);
    const copiedCells = get(copiedCellsAtom);
    return {
      isSelected: selectedCells.has(cellId),
      isCopied: copiedCells.has(cellId),
    };
  });
