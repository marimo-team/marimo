/* Copyright 2026 Marimo. All rights reserved. */

/** Notebook operations that edit the document and then adjust the editor. */

import { atom, type Getter, type Setter, useSetAtom } from "jotai";
import { useMemo } from "react";
import { scrollAndHighlightCell } from "@/components/editor/links/cell-link";
import type { DocumentModel, EditableDocument } from "@/core/notebook/document";
import type { CellColumnId } from "@/utils/id-tree";
import type { CellConfig } from "../network/types";
import { store } from "../state/jotai";
import { activeDocumentModelAtom } from "../session/active-notebook";
import { notebookAtom, useReducerActions } from "./cells";
import { CellId, SCRATCH_CELL_ID, SETUP_CELL_ID } from "./ids";
import { focusAndScrollCellIntoView } from "./scrollCellIntoView";

export interface CreateCellOptions {
  /** Place the cell after this one. */
  after?: CellId | null;
  /** Place the cell before this one. */
  before?: CellId | null;
  /** Without an anchor, the column to append to. The first by default. */
  endOf?: CellColumnId;
  /** The id to create with, for callers that refer to the cell before it exists. */
  id?: CellId;
  code?: string;
  name?: string;
  /** The cell's config. Its column follows from the placement. */
  config?: Partial<Omit<CellConfig, "column">>;
  /** Scroll to and focus the cell once it mounts. On by default. */
  focus?: boolean;
  /** Create nothing when a cell already has this code. */
  skipIfCodeExists?: boolean;
}

export type CreateCell = (options?: CreateCellOptions) => CellId | null;

function modelOf(get: Getter): DocumentModel {
  const model = get(activeDocumentModelAtom);
  if (!model) {
    throw new Error("The notebook has no document to edit");
  }
  return model;
}

function documentOf(get: Getter): EditableDocument {
  const document = get(modelOf(get).documentAtom);
  if (!document) {
    throw new Error("The notebook has no document to edit");
  }
  return document;
}

function hasCellWithCode(document: EditableDocument, code: string): boolean {
  for (const cell of document.cells.values()) {
    if (cell.code === code) {
      return true;
    }
  }
  return false;
}

/** Scroll to and focus the cell once it mounts. */
function focusWhenMounted(set: Setter, cellId: CellId): void {
  set(notebookAtom, (state) => ({ ...state, scrollKey: cellId }));
}

/** Create a cell. Returns its id, or null when it was skipped. */
export const createCellAtom = atom(
  null,
  (get, set, options: CreateCellOptions = {}): CellId | null => {
    const { code = "", focus = true } = options;
    const document = documentOf(get);
    if (options.skipIfCodeExists && hasCellWithCode(document, code)) {
      return null;
    }
    const { cellIds } = get(notebookAtom);

    // The document knows cells and order. Columns come from each cell's
    // `column` config, which the cell before it provides unless it starts a
    // column, so a cell placed first in a later column names its column.
    let placement: { after?: CellId; before?: CellId } = {};
    let column: number | null = null;
    if (options.after) {
      placement = { after: options.after };
    } else if (options.before) {
      const tree = cellIds.findWithId(options.before);
      const index = cellIds.indexOf(tree);
      placement = { before: options.before };
      if (index > 0 && tree.indexOfOrThrow(options.before) === 0) {
        column = index;
      }
    } else {
      const tree =
        (options.endOf && cellIds.get(options.endOf)) ?? cellIds.atOrThrow(0);
      if (tree.length > 0) {
        placement = { after: tree.last() };
      } else if (cellIds.colLength > 1) {
        column = cellIds.indexOf(tree);
      }
    }

    const id = options.id ?? CellId.create();
    const config = { ...options.config, column };
    set(modelOf(get).editAtom, (tx) => {
      tx.createCell({ id, code, name: options.name, config }, placement);
      // Only a column's first cell carries its index, as the file is written.
      if (column !== null && options.before) {
        tx.updateConfig(options.before, { column: null });
      }
    });
    if (focus) {
      focusWhenMounted(set, id);
      // Hidden code stays visible until the cell is blurred for the first time.
      if (config.hide_code) {
        set(notebookAtom, (state) => ({
          ...state,
          untouchedNewCells: new Set([...state.untouchedNewCells, id]),
        }));
      }
    }
    return id;
  },
);

/**
 * Focus the cell before or after `cellId`. Past the edge of the column,
 * create one there, unless `create` is false.
 */
export const moveToNextCellAtom = atom(
  null,
  (
    get,
    set,
    {
      cellId,
      before,
      create = true,
    }: { cellId: CellId; before: boolean; create?: boolean },
  ): void => {
    if (cellId === SCRATCH_CELL_ID) {
      return;
    }
    const notebook = get(notebookAtom);
    const column = notebook.cellIds.findWithId(cellId);
    const index = column.indexOfOrThrow(cellId);
    const nextIndex = before ? index - 1 : index + 1;
    if (nextIndex < 0 || nextIndex >= column.length) {
      if (create) {
        set(createCellAtom, before ? { before: cellId } : { after: cellId });
      }
      return;
    }
    const nextCellId = column.atOrThrow(nextIndex);
    const cell = notebook.cellData[nextCellId];
    focusAndScrollCellIntoView({
      cellId: nextCellId,
      cell: notebook.cellHandles[nextCellId],
      isCodeHidden:
        Boolean(cell.config.hide_code) &&
        !notebook.untouchedNewCells.has(nextCellId),
      codeFocus: before ? "bottom" : "top",
      variableName: undefined,
    });
  },
);

/** Focus the setup cell, creating it at the top with `code` if it is missing. */
export const addSetupCellAtom = atom(
  null,
  (get, set, { code }: { code?: string } = {}): void => {
    const { cellIds } = get(notebookAtom);
    if (cellIds.setupCellExists()) {
      focusWhenMounted(set, SETUP_CELL_ID);
      return;
    }
    const first = cellIds.atOrThrow(0).at(0);
    set(modelOf(get).editAtom, (tx) =>
      tx.createCell(
        { id: SETUP_CELL_ID, name: SETUP_CELL_ID, code: code ?? "" },
        first === undefined ? {} : { before: first },
      ),
    );
    focusWhenMounted(set, SETUP_CELL_ID);
  },
);

/**
 * Every notebook operation, for components. Stable for the store's lifetime.
 *
 * The reducer's actions are included while the reducer still has cases.
 * Outside React, set the atoms on the store directly.
 */
export function useCellActions() {
  // The session feeds the kernel's messages and the document into the
  // notebook through `useReducerActions`; components get the operations.
  const {
    handleCellMessage: _handleCellMessage,
    addLogs: _addLogs,
    reconcileDocument: _reconcileDocument,
    setLastRun: _setLastRun,
    resetCellRuntimes: _resetCellRuntimes,
    ...operations
  } = useReducerActions();
  const createCell = useSetAtom(createCellAtom);
  const moveToNextCell = useSetAtom(moveToNextCellAtom);
  const addSetupCell = useSetAtom(addSetupCellAtom);
  return useMemo(
    () => ({ ...operations, createCell, moveToNextCell, addSetupCell }),
    // The reducer's actions are stable for the store's lifetime.
    // oxlint-disable-next-line react-hooks/exhaustive-deps
    [createCell, moveToNextCell, addSetupCell],
  );
}

export type CellActions = ReturnType<typeof useCellActions>;

/** Scroll to the first cell that is currently running. */
export function notebookScrollToRunning() {
  const { cellIds, cellRuntime } = store.get(notebookAtom);
  const cellId = cellIds.inOrderIds.find(
    (id) => cellRuntime[id]?.status === "running",
  );
  if (!cellId) {
    return;
  }
  scrollAndHighlightCell(cellId, "focus");
}
