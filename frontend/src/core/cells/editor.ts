/* Copyright 2026 Marimo. All rights reserved. */

/** What only this browser knows about cells: hidden code showing for now, and editor state to restore. */

import { atom, useAtomValue } from "jotai";
import { useMemo } from "react";
import type { SerializedEditorState } from "../codemirror/types";
import type { CellId } from "./ids";

/**
 * Hidden cells whose code is showing for now: a cell being edited, one just
 * created, or one just made hidden. Blurring the cell hides it again.
 */
export const shownHiddenCodeAtom = atom<ReadonlySet<CellId>>(new Set<CellId>());

export const useShowsHiddenCode = (cellId: CellId) =>
  useAtomValue(
    useMemo(
      () => atom((get) => get(shownHiddenCodeAtom).has(cellId)),
      [cellId],
    ),
  );

/** Whether a cell's code is hidden on the page. */
export function isCodeHidden(
  hideCode: boolean | undefined,
  shown: ReadonlySet<CellId>,
  cellId: CellId,
): boolean {
  return Boolean(hideCode) && !shown.has(cellId);
}

export const showHiddenCodeAtom = atom(
  null,
  (_get, set, { cellId }: { cellId: CellId }): void => {
    set(shownHiddenCodeAtom, (cells) => new Set([...cells, cellId]));
  },
);

export const hideShownCodeAtom = atom(
  null,
  (_get, set, { cellId }: { cellId: CellId }): void => {
    set(shownHiddenCodeAtom, (cells) => {
      const next = new Set(cells);
      next.delete(cellId);
      return next;
    });
  },
);

/**
 * Editor state for cells about to mount again, such as a cell undo brings
 * back. The editor takes its entry when it mounts.
 */
export const restoredEditorStatesAtom = atom<
  ReadonlyMap<CellId, SerializedEditorState>
>(new Map<CellId, SerializedEditorState>());

export const useRestoredEditorState = (cellId: CellId) =>
  useAtomValue(
    useMemo(
      () => atom((get) => get(restoredEditorStatesAtom).get(cellId) ?? null),
      [cellId],
    ),
  );

export const takeRestoredEditorStateAtom = atom(
  null,
  (_get, set, { cellId }: { cellId: CellId }): void => {
    set(restoredEditorStatesAtom, (states) => {
      const next = new Map(states);
      next.delete(cellId);
      return next;
    });
  },
);
