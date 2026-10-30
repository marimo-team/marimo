/* Copyright 2026 Marimo. All rights reserved. */

/** Notebook operations that edit the document and then adjust the editor. */

import { historyField } from "@codemirror/commands";
import { atom, type Getter, type Setter, useSetAtom } from "jotai";
import { useMemo } from "react";
import { scrollAndHighlightCell } from "@/components/editor/links/cell-link";
import type { EditableDocument } from "@/core/notebook/document";
import { Logger } from "@/utils/Logger";
import { clamp } from "@/utils/math";
import { prepareCellCodeUpdate } from "../codemirror/language/cell-code";
import { splitEditor } from "../codemirror/language/utils";
import type { SerializedEditorState } from "../codemirror/types";
import { canCollapseOutline } from "../dom/outline";
import type { CellConfig } from "../network/types";
import { store } from "../state/jotai";
import {
  addColumnAtom,
  addColumnBreakpointAtom,
  compactColumnsAtom,
  deleteColumnAtom,
  dropCellOverCellAtom,
  dropCellOverColumnAtom,
  mergeAllColumnsAtom,
  moveCellAtom,
  moveColumnAtom,
  moveCellsRelativeToAtom,
  moveCellToIndexAtom,
  placeCells,
  sendToBottomAtom,
  sendToTopAtom,
} from "./arrange";
import {
  type DeletedCell,
  notebookAtom,
  notebookReducer,
  releaseCellAtoms,
  useReducerActions,
} from "./cells";
import { resolveColumns } from "./columns";
import { documentOf, focusWhenMounted, modelOf } from "./edit";
import {
  isCodeHidden,
  restoredEditorStatesAtom,
  shownHiddenCodeAtom,
} from "./editor";
import { CellId, SCRATCH_CELL_ID, SETUP_CELL_ID } from "./ids";
import {
  type CellColumnId,
  collapsedAtom,
  columnOf,
  findColumn,
  foldOf,
  foldsHiding,
  layoutAtom,
} from "./layout";
import {
  focusAndScrollCellIntoView,
  scrollToBottom,
  scrollToTop,
} from "./scrollCellIntoView";

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

function hasCellWithCode(document: EditableDocument, code: string): boolean {
  for (const cell of document.cells.values()) {
    if (cell.code === code) {
      return true;
    }
  }
  return false;
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
    const layout = get(layoutAtom);

    // The document knows cells and order. Columns come from each cell's
    // `column` config, which the cell before it provides unless it starts a
    // column, so a cell placed first in a later column names its column.
    let placement: { after?: CellId; before?: CellId } = {};
    let column: number | null = null;
    if (options.after) {
      // A folded header hides the cells after it, so a cell placed after
      // the header goes after its fold. Any section that holds the anchor
      // holds the new cell too, so when it is to be focused, those open.
      const fold = foldOf(layout, options.after);
      placement = { after: fold?.at(-1) ?? options.after };
      const sections = foldsHiding(layout, options.after);
      if (fold) {
        sections.push(options.after);
      }
      if (focus && sections.length > 0) {
        set(collapsedAtom, (collapsed) => {
          const next = new Set(collapsed);
          for (const header of sections) {
            next.delete(header);
          }
          return next;
        });
      }
    } else if (options.before) {
      const target = columnOf(layout, options.before);
      const index = layout.columns.indexOf(target);
      placement = { before: options.before };
      if (index > 0 && target.ids[0] === options.before) {
        column = index;
      }
    } else {
      const target =
        (options.endOf && findColumn(layout, options.endOf)) ??
        layout.columns[0];
      const last = target.ids.at(-1);
      if (last !== undefined) {
        placement = { after: last };
      } else if (layout.columns.length > 1) {
        column = layout.columns.indexOf(target);
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
      // Hidden code stays showing until the cell is blurred for the first time.
      if (config.hide_code) {
        set(shownHiddenCodeAtom, (cells) => new Set([...cells, id]));
      }
    }
    return id;
  },
);

/**
 * Split a cell at its cursor. The text before stays, the text after
 * becomes a new cell below, which is focused. Returns the new cell's id,
 * or null for a cell without an editor.
 */
export const splitCellAtom = atom(
  null,
  (get, set, { cellId }: { cellId: CellId }): CellId | null => {
    const view = get(notebookAtom).cellHandles[cellId]?.current?.editorView;
    if (!view) {
      return null;
    }
    const { beforeCursorCode, afterCursorCode } = splitEditor(view);
    const update = prepareCellCodeUpdate(view.state, beforeCursorCode);
    if (update) {
      view.dispatch(update);
    }
    const id = CellId.create();
    set(modelOf(get).editAtom, (tx) => {
      tx.setCode(cellId, beforeCursorCode);
      tx.createCell({ id, code: afterCursorCode }, { after: cellId });
    });
    clearOutput(set, cellId);
    focusWhenMounted(set, id);
    return id;
  },
);

/** Undo a split: the cell takes its code back and the cell split off goes. */
export const undoSplitCellAtom = atom(
  null,
  (
    get,
    set,
    {
      cellId,
      newCellId,
      snapshot,
    }: { cellId: CellId; newCellId: CellId; snapshot: string },
  ): void => {
    const view = get(notebookAtom).cellHandles[cellId]?.current?.editorView;
    const update = view && prepareCellCodeUpdate(view.state, snapshot);
    if (view && update) {
      view.dispatch(update);
    }
    const document = documentOf(get);
    set(modelOf(get).editAtom, (tx) => {
      tx.setCode(cellId, snapshot);
      if (document.cells.has(newCellId)) {
        tx.deleteCell(newCellId);
      }
    });
    releaseCellAtoms(newCellId);
    clearOutput(set, cellId);
  },
);

/** The output belonged to the code before the change; neither version has run. */
function clearOutput(set: Setter, cellId: CellId): void {
  set(notebookAtom, (state) =>
    notebookReducer(state, { type: "clearCellOutput", payload: { cellId } }),
  );
}

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
    const { visible } = columnOf(get(layoutAtom), cellId);
    const index = visible.indexOf(cellId);
    const nextIndex = before ? index - 1 : index + 1;
    if (index === -1 || nextIndex < 0 || nextIndex >= visible.length) {
      if (create) {
        set(createCellAtom, before ? { before: cellId } : { after: cellId });
      }
      return;
    }
    focusOnPage(get, visible[nextIndex], before ? "bottom" : "top");
  },
);

/** Focus a cell on the page, scrolling to it. */
function focusOnPage(
  get: Getter,
  cellId: CellId,
  codeFocus: "top" | "bottom" | undefined,
): void {
  const notebook = get(notebookAtom);
  focusAndScrollCellIntoView({
    cellId,
    cell: notebook.cellHandles[cellId],
    isCodeHidden: isCodeHidden(
      notebook.cellData[cellId]?.config.hide_code,
      get(shownHiddenCodeAtom),
      cellId,
    ),
    codeFocus,
    variableName: undefined,
  });
}

/** Focus the visible cell before, after, or at `cellId` within its column. */
export const focusCellAtom = atom(
  null,
  (
    get,
    _set,
    { cellId, where }: { cellId: CellId; where: "before" | "after" | "exact" },
  ): void => {
    const { visible } = columnOf(get(layoutAtom), cellId);
    const index = visible.indexOf(cellId);
    if (index === -1) {
      return;
    }
    const offset = where === "before" ? -1 : where === "after" ? 1 : 0;
    const target = clamp(index + offset, 0, visible.length - 1);
    focusOnPage(get, visible[target], where === "after" ? "top" : "bottom");
  },
);

/** Focus the first visible cell of the first column. */
export const focusTopCellAtom = atom(null, (get): void => {
  const first = get(layoutAtom).columns[0]?.visible[0];
  if (first === undefined) {
    return;
  }
  focusOnPage(get, first, undefined);
  scrollToTop();
});

/** Focus the last visible cell of the last column. */
export const focusBottomCellAtom = atom(null, (get): void => {
  const last = get(layoutAtom).columns.at(-1)?.visible.at(-1);
  if (last === undefined) {
    return;
  }
  focusOnPage(get, last, undefined);
  scrollToBottom();
});

// Folding ---------------------------------------------------------------------
//
// A folded header hides the cells of its section. Which headers are folded is
// editor state; the section each one hides derives from the outlines.

/** Fold the section under `cellId`, if its output has a heading. */
export const collapseCellAtom = atom(
  null,
  (get, set, { cellId }: { cellId: CellId }): void => {
    if (!canCollapseOutline(get(notebookAtom).cellRuntime[cellId]?.outline)) {
      return;
    }
    set(collapsedAtom, (collapsed) => new Set([...collapsed, cellId]));
    focusWhenMounted(set, cellId);
  },
);

/** Unfold the section under `cellId`. */
export const expandCellAtom = atom(
  null,
  (_get, set, { cellId }: { cellId: CellId }): void => {
    set(collapsedAtom, (collapsed) => {
      const next = new Set(collapsed);
      next.delete(cellId);
      return next;
    });
    focusWhenMounted(set, cellId);
  },
);

/** Fold every section in the notebook. */
export const collapseAllCellsAtom = atom(null, (get, set): void => {
  const { cellIds, cellRuntime } = get(notebookAtom);
  set(
    collapsedAtom,
    new Set(
      cellIds.filter((id) => canCollapseOutline(cellRuntime[id]?.outline)),
    ),
  );
});

/** Unfold every section. */
export const expandAllCellsAtom = atom(null, (_get, set): void => {
  set(collapsedAtom, new Set());
});

/** Unfold whatever hides `cellId`, so it is on the page. */
export const showCellIfHiddenAtom = atom(
  null,
  (get, set, { cellId }: { cellId: CellId }): void => {
    const hiding = foldsHiding(get(layoutAtom), cellId);
    if (hiding.length === 0) {
      return;
    }
    set(collapsedAtom, (collapsed) => {
      const next = new Set(collapsed);
      for (const header of hiding) {
        next.delete(header);
      }
      return next;
    });
  },
);

/** Focus the setup cell, creating it at the top with `code` if it is missing. */
export const addSetupCellAtom = atom(
  null,
  (get, set, { code }: { code?: string } = {}): void => {
    const { cellIds } = get(notebookAtom);
    if (cellIds.includes(SETUP_CELL_ID)) {
      focusWhenMounted(set, SETUP_CELL_ID);
      return;
    }
    const first = cellIds[0];
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

    // Focus the nearest visible survivor in the column, looking up before down.
    const first = deleting[0].id as CellId;
    const column = columnOf(get(layoutAtom), first);
    const ids = column.visible.includes(first) ? column.visible : column.ids;
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
    set(shownHiddenCodeAtom, (cells) =>
      cells.size === 0
        ? cells
        : new Set([...cells].filter((id) => !gone.has(id))),
    );
    set(notebookAtom, (state) => ({
      ...state,
      history: [...state.history, { type: "delete", cells }],
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
    set(notebookAtom, (state) => ({
      ...state,
      history: state.history.slice(0, -1),
    }));
    placeCells(get, set, last.cellIds, last.placements);
    focusWhenMounted(set, last.cellIds[0]);
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
  // The editors take their history back when they mount.
  set(restoredEditorStatesAtom, (states) => {
    const next = new Map(states);
    for (const { cell, serializedEditorState } of last.cells) {
      if (serializedEditorState !== null) {
        next.set(cell.id as CellId, serializedEditorState);
      }
    }
    return next;
  });
  set(notebookAtom, (state) => ({
    ...state,
    history: state.history.slice(0, -1),
    scrollKey: last.cells[0].cell.id as CellId,
  }));
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
  const focusCell = useSetAtom(focusCellAtom);
  const focusTopCell = useSetAtom(focusTopCellAtom);
  const focusBottomCell = useSetAtom(focusBottomCellAtom);
  const collapseCell = useSetAtom(collapseCellAtom);
  const expandCell = useSetAtom(expandCellAtom);
  const collapseAllCells = useSetAtom(collapseAllCellsAtom);
  const expandAllCells = useSetAtom(expandAllCellsAtom);
  const showCellIfHidden = useSetAtom(showCellIfHiddenAtom);
  const moveCell = useSetAtom(moveCellAtom);
  const moveCellToIndex = useSetAtom(moveCellToIndexAtom);
  const moveCellsRelativeTo = useSetAtom(moveCellsRelativeToAtom);
  const dropCellOverCell = useSetAtom(dropCellOverCellAtom);
  const dropCellOverColumn = useSetAtom(dropCellOverColumnAtom);
  const sendToTop = useSetAtom(sendToTopAtom);
  const sendToBottom = useSetAtom(sendToBottomAtom);
  const addColumn = useSetAtom(addColumnAtom);
  const addColumnBreakpoint = useSetAtom(addColumnBreakpointAtom);
  const deleteColumn = useSetAtom(deleteColumnAtom);
  const mergeAllColumns = useSetAtom(mergeAllColumnsAtom);
  const compactColumns = useSetAtom(compactColumnsAtom);
  const moveColumn = useSetAtom(moveColumnAtom);
  const splitCell = useSetAtom(splitCellAtom);
  const undoSplitCell = useSetAtom(undoSplitCellAtom);
  return useMemo(
    () => ({
      ...operations,
      splitCell,
      undoSplitCell,
      addColumn,
      addColumnBreakpoint,
      deleteColumn,
      mergeAllColumns,
      compactColumns,
      moveColumn,
      moveCell,
      moveCellToIndex,
      moveCellsRelativeTo,
      dropCellOverCell,
      dropCellOverColumn,
      sendToTop,
      sendToBottom,
      createCell,
      moveToNextCell,
      addSetupCell,
      deleteCells,
      undoDeleteCell,
      focusCell,
      focusTopCell,
      focusBottomCell,
      collapseCell,
      expandCell,
      collapseAllCells,
      expandAllCells,
      showCellIfHidden,
    }),
    // The reducer's actions and the atom setters are stable for the store's lifetime.
    // oxlint-disable-next-line react-hooks/exhaustive-deps
    [],
  );
}

export type CellActions = ReturnType<typeof useCellActions>;

/** Scroll to the first cell that is currently running. */
export function notebookScrollToRunning() {
  const { cellIds, cellRuntime } = store.get(notebookAtom);
  const cellId = cellIds.find((id) => cellRuntime[id]?.status === "running");
  if (!cellId) {
    return;
  }
  scrollAndHighlightCell(cellId, "focus");
}
