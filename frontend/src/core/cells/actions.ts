/* Copyright 2026 Marimo. All rights reserved. */

/** Notebook operations that edit the document and then adjust the editor. */

import { historyField } from "@codemirror/commands";
import { atom, type Getter, type Setter, useSetAtom } from "jotai";
import { useMemo } from "react";
import { scrollAndHighlightCell } from "@/components/editor/links/cell-link";
import type { DocumentModel, EditableDocument } from "@/core/notebook/document";
import type { CellColumnId } from "@/utils/id-tree";
import { Logger } from "@/utils/Logger";
import type { SerializedEditorState } from "../codemirror/types";
import type { CellConfig } from "../network/types";
import { store } from "../state/jotai";
import { activeDocumentModelAtom } from "../session/active-notebook";
import {
  type DeletedCell,
  notebookAtom,
  notebookReducer,
  releaseCellAtoms,
  useReducerActions,
} from "./cells";
import { resolveColumns } from "./columns";
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
 * Delete cells, keeping them in the history for undo. The notebook keeps at
 * least one cell. Returns false when nothing was deleted.
 */
export const deleteCellsAtom = atom(
  null,
  (get, set, { cellIds }: { cellIds: CellId[] }): boolean => {
    const document = documentOf(get);
    const notebook = get(notebookAtom);
    const requested = new Set(cellIds);
    for (const id of cellIds) {
      if (!document.cells.has(id)) {
        // Expected for kernel-only cells or a cell another client removed.
        Logger.warn("Skipping delete for missing cellId", { cellId: id });
      }
    }
    const order = document.order as CellId[];
    const deleting = order.flatMap((id) => {
      const cell = document.cells.get(id);
      return cell !== undefined && requested.has(id) ? [cell] : [];
    });
    if (deleting.length === order.length) {
      deleting.pop();
    }
    if (deleting.length === 0) {
      return false;
    }
    const gone = new Set(deleting.map((cell) => cell.id as CellId));
    const firstSurvivor = order.find((id) => !gone.has(id));

    const cells: DeletedCell[] = deleting.map((cell) => {
      const id = cell.id as CellId;
      const index = order.indexOf(id);
      const code = cell.code ?? notebook.cellData[id]?.code ?? "";
      const editorView = notebook.cellHandles[id]?.current?.editorView;
      const serializedEditorState: SerializedEditorState | null =
        editorView?.state.toJSON({ history: historyField }) ?? null;
      if (serializedEditorState) {
        serializedEditorState.doc = code;
      }
      return {
        cell: { id, code, name: cell.name, config: cell.config },
        // Anchor to the cell before it, which undo restores first if it is
        // also being deleted. The first cell anchors to the next survivor.
        placement:
          index > 0 ? { after: order[index - 1] } : { before: firstSurvivor },
        serializedEditorState,
      };
    });

    // Focus the nearest survivor in the column, looking up before down.
    const first = deleting[0].id as CellId;
    const ids = notebook.cellIds.findWithId(first).inOrderIds;
    const at = ids.indexOf(first);
    const scrollKey =
      ids.slice(0, at).findLast((id) => !gone.has(id)) ??
      ids.slice(at + 1).find((id) => !gone.has(id)) ??
      null;

    const columns = resolveColumns(document);
    set(modelOf(get).editAtom, (tx) => {
      // A cell without a `column` config takes the column of the cell before
      // it, so a survivor that followed a deleted cell names its own.
      let previous: CellId | null = null;
      let followsDeleted = false;
      for (const id of order) {
        if (gone.has(id)) {
          followsDeleted = true;
          continue;
        }
        const inherited = previous === null ? 0 : columns.get(previous);
        if (
          followsDeleted &&
          document.cells.get(id)?.config.column == null &&
          inherited !== columns.get(id)
        ) {
          tx.updateConfig(id, { column: columns.get(id) });
        }
        previous = id;
        followsDeleted = false;
      }
      for (const id of gone) {
        tx.deleteCell(id);
      }
    });
    for (const id of gone) {
      releaseCellAtoms(id);
    }
    set(notebookAtom, (state) => ({
      ...state,
      history: [...state.history, { type: "delete", cells }],
      untouchedNewCells: new Set(
        [...state.untouchedNewCells].filter((id) => !gone.has(id)),
      ),
      scrollKey,
    }));
    return true;
  },
);

/** Undo the last deletion or move. */
export const undoDeleteCellAtom = atom(null, (get, set): void => {
  const last = get(notebookAtom).history.at(-1);
  if (last === undefined) {
    return;
  }
  if (last.type === "move") {
    set(notebookAtom, (state) =>
      notebookReducer(
        { ...state, history: state.history.slice(0, -1) },
        { type: "undoMoveCells", payload: last },
      ),
    );
    return;
  }
  const model = modelOf(get);
  const before = documentOf(get);
  set(model.editAtom, (tx) => {
    // Each cell anchors to the one before it, restored just before it. An
    // anchor another client has removed since falls back to the end.
    const restored = new Set<string>();
    for (const { cell, placement } of last.cells) {
      const anchor = placement.after ?? placement.before;
      const anchored =
        anchor === undefined ||
        before.cells.has(anchor) ||
        restored.has(anchor);
      tx.createCell(cell, anchored ? placement : {});
      restored.add(cell.id);
    }
  });
  // Subscribers hear of the edit after the outermost set, so the notebook
  // has not followed the document yet. Catch it up to reach the new cells.
  const document = get(model.documentAtom);
  if (document !== null) {
    set(notebookAtom, (state) =>
      notebookReducer(state, { type: "reconcileDocument", payload: document }),
    );
  }
  set(notebookAtom, (state) => {
    let { cellData } = state;
    for (const { cell, serializedEditorState } of last.cells) {
      const id = cell.id as CellId;
      if (serializedEditorState !== null && cellData[id] !== undefined) {
        cellData = {
          ...cellData,
          [id]: { ...cellData[id], serializedEditorState },
        };
      }
    }
    return {
      ...state,
      cellData,
      history: state.history.slice(0, -1),
      scrollKey: last.cells[0].cell.id as CellId,
    };
  });
});

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
  const deleteCells = useSetAtom(deleteCellsAtom);
  const undoDeleteCell = useSetAtom(undoDeleteCellAtom);
  return useMemo(
    () => ({
      ...operations,
      createCell,
      moveToNextCell,
      addSetupCell,
      deleteCells,
      undoDeleteCell,
    }),
    // The reducer's actions are stable for the store's lifetime.
    // oxlint-disable-next-line react-hooks/exhaustive-deps
    [createCell, moveToNextCell, addSetupCell, deleteCells, undoDeleteCell],
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
