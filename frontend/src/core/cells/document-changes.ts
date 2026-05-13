/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Document changes: the bridge between notebook reducer actions and the
 * document transaction wire format.
 *
 * Pure functions:
 * - toDocumentChanges: reducer action + state diff → document changes
 * - fromDocumentChanges: document changes → reducer actions
 * - cancelledCellIds: detect create+delete cancellations
 *
 * Impure wrappers (for use by the reducer middleware and websocket):
 * - documentTransactionMiddleware: debounces and sends changes to the server
 * - applyTransactionChanges: dispatches actions from incoming changes
 */

import { debounce } from "lodash-es";
import { assertNever } from "@/utils/assertNever";
import type { DispatchedActionOf } from "@/utils/createReducer";
import { Logger } from "@/utils/Logger";
import type { NotificationMessageData } from "../kernel/messages";
import { kioskModeAtom } from "../mode";
import { getRequestClient } from "../network/requests";
import type { NotebookDocumentTransactionRequest } from "../network/types";
import { store } from "../state/jotai";
import type { CellActions, NotebookState } from "./cells";
import type { CellId } from "./ids";
import { SCRATCH_CELL_ID } from "./ids";
import type { CellData } from "./types";

export type DocumentChange =
  NotebookDocumentTransactionRequest["changes"][number];

type Transaction =
  NotificationMessageData<"notebook-document-transaction">["transaction"];
type TransactionChange = Transaction["changes"][number];

export type CellAction = DispatchedActionOf<CellActions>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Look up a cell in state by ID. Logs a warning and returns undefined
 * if the cell doesn't exist.
 */
function getCell(
  cellId: CellId | undefined,
  state: NotebookState,
): CellData | undefined {
  if (!cellId) {
    Logger.warn("getCell: cellId is undefined");
    return undefined;
  }
  const cell = state.cellData[cellId];
  if (!cell) {
    Logger.warn(`getCell: cell ${cellId} not found in state`);
    return undefined;
  }
  return cell;
}

/**
 * Derive the position anchor for a cell from the notebook state.
 * Returns `{ after: prevId }` if there's a cell before it,
 * `{ before: nextId }` if it's the first cell, or `undefined` if it's alone.
 */
function anchorOf(
  cellId: CellId,
  state: NotebookState,
): { after: CellId } | { before: CellId } | undefined {
  const ids = state.cellIds.inOrderIds;
  const idx = ids.indexOf(cellId);
  if (idx > 0) {
    return { after: ids[idx - 1] };
  }
  if (idx === 0 && ids.length > 1) {
    return { before: ids[1] };
  }
  return undefined;
}

/**
 * Build a map from cellId → column index for all cells in the state.
 */
function columnIndexMap(state: NotebookState): Map<CellId, number> {
  const map = new Map<CellId, number>();
  const columns = state.cellIds.getColumns();
  for (const [col, column] of columns.entries()) {
    for (const id of column.inOrderIds) {
      map.set(id, col);
    }
  }
  return map;
}

/**
 * Find cells that were added between prevState and newState and return
 * create-cell changes for each, with position derived from newState.
 */
function newCellChanges(
  prevState: NotebookState,
  newState: NotebookState,
): DocumentChange[] {
  const prevIds = new Set(prevState.cellIds.inOrderIds);
  const changes: DocumentChange[] = [];
  for (const id of newState.cellIds.inOrderIds) {
    if (!prevIds.has(id)) {
      const cell = getCell(id, newState);
      if (cell) {
        changes.push({
          type: "create-cell",
          cellId: cell.id,
          code: cell.code,
          name: cell.name,
          config: cell.config,
          ...anchorOf(cell.id, newState),
        });
      }
    }
  }
  return changes;
}

/**
 * Find cells that were removed between prevState and newState and return
 * delete-cell changes for each.
 */
function deletedCellChanges(
  prevState: NotebookState,
  newState: NotebookState,
): DocumentChange[] {
  const newIds = new Set(newState.cellIds.inOrderIds);
  const changes: DocumentChange[] = [];
  for (const id of prevState.cellIds.inOrderIds) {
    if (!newIds.has(id)) {
      changes.push({ type: "delete-cell", cellId: id });
    }
  }
  return changes;
}

/**
 * Produce set-config changes for cells whose column index changed between
 * prevState and newState, plus a reorder-cells change for the new ordering.
 */
function columnChanges(
  prevState: NotebookState,
  newState: NotebookState,
): DocumentChange[] {
  const prevColumns = columnIndexMap(prevState);
  const newColumns = columnIndexMap(newState);
  const changes: DocumentChange[] = [];

  for (const [cellId, newCol] of newColumns) {
    const prevCol = prevColumns.get(cellId);
    if (prevCol !== newCol) {
      const cell = getCell(cellId, newState);
      changes.push({
        type: "set-config",
        cellId: cellId,
        column: newCol,
        disabled: cell?.config.disabled ?? false,
        hideCode: cell?.config.hide_code ?? false,
      });
    }
  }

  changes.push({
    type: "reorder-cells",
    cellIds: newState.cellIds.inOrderIds,
  });

  return changes;
}

// ---------------------------------------------------------------------------
// toDocumentChanges: action + state → changes
// ---------------------------------------------------------------------------

/**
 * Given a reducer action and the before/after notebook state, return the
 * document changes that represent the diff. Returns an empty array for
 * actions that don't affect document structure.
 */
export function toDocumentChanges(
  prevState: NotebookState,
  newState: NotebookState,
  action: DispatchedActionOf<CellActions>,
): DocumentChange[] {
  switch (action.type) {
    // createNewCell → create-cell
    // Reads code, name, and config from the newly created cell in newState.
    // Position is derived from newState via anchorOf (after or before neighbor).
    case "createNewCell":
      return newCellChanges(prevState, newState);

    // deleteCell → delete-cell
    // Direct 1:1 mapping. Only the cellId is needed.
    case "deleteCell":
      return [{ type: "delete-cell", cellId: action.payload.cellId }];

    // moveCell/sendToTop/sendToBottom → move-cell
    // All three change a single cell's position. We derive the final
    // position from newState via anchorOf rather than interpreting the
    // action's before/direction payload.
    case "moveCell":
    case "sendToTop":
    case "sendToBottom": {
      const { cellId } = action.payload;
      return [
        {
          type: "move-cell",
          cellId: cellId,
          ...anchorOf(cellId, newState),
        },
      ];
    }

    // dropCellOverCell/dropCellOverColumn/moveCellToIndex → set-config + reorder-cells
    // Drag-and-drop reorders can move cells within or across columns.
    // We emit config changes for cells whose column changed, then
    // the full ordering.
    case "dropCellOverCell":
    case "dropCellOverColumn":
    case "moveCellToIndex":
      return columnChanges(prevState, newState);

    // updateCellCode → set-code
    // Reads the code from newState via getCell.
    case "updateCellCode": {
      const cell = getCell(action.payload.cellId, newState);
      if (!cell) {
        return [];
      }
      return [
        {
          type: "set-code",
          cellId: cell.id,
          code: cell.code,
        },
      ];
    }

    // updateCellName → set-name
    // Reads the name from newState via getCell.
    case "updateCellName": {
      const cell = getCell(action.payload.cellId, newState);
      if (!cell) {
        return [];
      }
      return [
        {
          type: "set-name",
          cellId: cell.id,
          name: cell.name,
        },
      ];
    }

    // updateCellConfig → set-config
    // SetConfig is full-replacement: emit the cell's complete config from
    // newState (which already merged the action's partial payload).
    case "updateCellConfig": {
      const { cellId } = action.payload;
      const cell = getCell(cellId, newState);
      if (!cell) {
        return [];
      }
      return [
        {
          type: "set-config",
          cellId: cellId,
          column: cell.config.column ?? null,
          disabled: cell.config.disabled ?? false,
          hideCode: cell.config.hide_code ?? false,
        },
      ];
    }

    // Column structure changes → set-config + reorder-cells
    // All of these change column layout. We emit config changes for
    // cells whose column index changed, then the full ordering.
    case "dropOverNewColumn":
    case "moveColumn":
    case "addColumnBreakpoint":
    case "deleteColumn":
    case "mergeAllColumns":
    case "compactColumns":
      return columnChanges(prevState, newState);

    // addColumn creates a new column with a new empty cell.
    // Emits create-cell for the new cell plus column layout changes.
    case "addColumn":
      return [
        ...newCellChanges(prevState, newState),
        ...columnChanges(prevState, newState),
      ];

    // undoDeleteCell restores a deleted cell from history.
    case "undoDeleteCell": {
      const changes = newCellChanges(prevState, newState);
      const colChanges = columnChanges(prevState, newState);
      // Only include column changes if layout actually changed
      // (colChanges always has at least a reorder-cells change)
      return colChanges.length > 1 ? [...changes, ...colChanges] : changes;
    }

    // splitCell: original cell gets truncated code, new cell gets remainder.
    case "splitCell": {
      const { cellId } = action.payload;
      const cell = getCell(cellId, newState);
      if (!cell) {
        return [];
      }
      return [
        { type: "set-code", cellId, code: cell.code },
        ...newCellChanges(prevState, newState),
      ];
    }

    // undoSplitCell: merge next cell back into current, delete the next cell.
    case "undoSplitCell": {
      const { cellId } = action.payload;
      const cell = getCell(cellId, newState);
      if (!cell) {
        return [];
      }
      return [
        { type: "set-code", cellId, code: cell.code },
        ...deletedCellChanges(prevState, newState),
      ];
    }

    // moveToNextCell: may create a new cell at boundary.
    case "moveToNextCell":
      return newCellChanges(prevState, newState);

    // addSetupCellIfDoesntExist: creates setup cell if missing.
    case "addSetupCellIfDoesntExist":
      return newCellChanges(prevState, newState);

    // UI-only actions — no document changes.
    case "focusCell":
    case "focusTopCell":
    case "focusBottomCell":
    case "scrollToTarget":
    case "showCellIfHidden":
    case "markTouched":
    case "markUntouched":
      return [];

    // Kernel/runtime state — never produces document changes.
    case "prepareForRun":
    case "handleCellMessage":
    case "setCellIds":
    case "rebuildCellColumns":
    case "setCellCodes":
    case "setCells":
    case "setStdinResponse":
    case "clearSerializedEditorState":
    case "clearCellOutput":
    case "clearCellConsoleOutput":
    case "clearAllCellOutputs":
    case "clearLogs":
      return [];

    // Editor UI state — no document changes.
    case "foldAll":
    case "unfoldAll":
    case "collapseCell":
    case "expandCell":
    case "collapseAllCells":
    case "expandAllCells":
      return [];

    default:
      assertNever(action);
  }
}

// ---------------------------------------------------------------------------
// fromDocumentChanges: changes → actions
// ---------------------------------------------------------------------------

/**
 * Find cell IDs that are both created and deleted in a set of changes.
 * These cancel out and should be skipped.
 */
export function cancelledCellIds(changes: TransactionChange[]): Set<string> {
  const created = new Set<string>();
  const deleted = new Set<string>();
  for (const change of changes) {
    if (change.type === "create-cell") {
      created.add(change.cellId);
    } else if (change.type === "delete-cell") {
      deleted.add(change.cellId);
    }
  }
  return created.intersection(deleted);
}

/**
 * Given document changes (from the server) and the current cell ordering,
 * return the reducer actions that apply them to frontend state.
 */
export function fromDocumentChanges(
  changes: TransactionChange[],
  getCurrentCellIds: () => CellId[],
): CellAction[] {
  const actions: CellAction[] = [];

  for (const change of changes) {
    switch (change.type) {
      // create-cell → createNewCell + updateCellName + updateCellConfig
      // Translates the change's before/after anchor into createNewCell's
      // cellId+before pair. The change carries code, name, and a full CellConfig.
      // createNewCell only accepts hideCode, so name and remaining config
      // (disabled, column) are applied as separate follow-up actions.
      case "create-cell": {
        let cellId: CellId | "__end__" = "__end__";
        let before = false;
        if (change.after) {
          cellId = change.after;
          before = false;
        } else if (change.before) {
          cellId = change.before;
          before = true;
        }
        actions.push({
          type: "createNewCell",
          payload: {
            cellId,
            before,
            code: change.code,
            newCellId: change.cellId,
            autoFocus: false,
            hideCode: change.config?.hide_code ?? false,
          },
        });
        if (change.name) {
          actions.push({
            type: "updateCellName",
            payload: { cellId: change.cellId, name: change.name },
          });
        }
        if (change.config?.disabled != null || change.config?.column != null) {
          actions.push({
            type: "updateCellConfig",
            payload: {
              cellId: change.cellId,
              config: {
                ...(change.config.disabled != null && {
                  disabled: change.config.disabled,
                }),
                ...(change.config.column != null && {
                  column: change.config.column,
                }),
              },
            },
          });
        }
        break;
      }

      // delete-cell → deleteCell
      // Direct 1:1 mapping.
      case "delete-cell":
        actions.push({
          type: "deleteCell",
          payload: { cellId: change.cellId },
        });
        break;

      // move-cell → setCellIds
      // Reconstructs the full ordering by splicing the cell out and
      // reinserting it relative to the before/after anchor. Falls back
      // to appending (after) or prepending (before) if the anchor is
      // missing. No-ops if the cell itself doesn't exist.
      case "move-cell": {
        const ids = [...getCurrentCellIds()];
        const cellId = change.cellId;
        const idx = ids.indexOf(cellId);
        if (idx < 0) {
          break;
        }
        ids.splice(idx, 1);
        if (change.after) {
          const afterIdx = ids.indexOf(change.after);
          if (afterIdx >= 0) {
            ids.splice(afterIdx + 1, 0, cellId);
          } else {
            ids.push(cellId);
          }
        } else if (change.before) {
          const beforeIdx = ids.indexOf(change.before);
          if (beforeIdx >= 0) {
            ids.splice(beforeIdx, 0, cellId);
          } else {
            ids.unshift(cellId);
          }
        } else {
          ids.push(cellId);
        }
        actions.push({
          type: "setCellIds",
          payload: { cellIds: ids },
        });
        break;
      }

      // reorder-cells → setCellIds
      // Replaces the full cell ordering. Used for drag-and-drop and
      // bulk reorders where expressing individual moves is impractical.
      case "reorder-cells":
        actions.push({
          type: "setCellIds",
          payload: { cellIds: change.cellIds },
        });
        break;

      // set-code → setCellCodes
      // Marks the code as stale (codeIsStale: true) since it came from
      // an external source and hasn't been executed yet.
      case "set-code":
        actions.push({
          type: "setCellCodes",
          payload: {
            ids: [change.cellId],
            codes: [change.code],
            codeIsStale: true,
          },
        });
        break;

      // set-name → updateCellName
      // Direct 1:1 mapping.
      case "set-name":
        actions.push({
          type: "updateCellName",
          payload: { cellId: change.cellId, name: change.name },
        });
        break;

      // set-config → updateCellConfig
      case "set-config":
        actions.push({
          type: "updateCellConfig",
          payload: {
            cellId: change.cellId,
            config: {
              column: change.column,
              disabled: change.disabled,
              hide_code: change.hideCode,
            },
          },
        });
        break;
    }
  }

  return actions;
}

// ---------------------------------------------------------------------------
// Middleware: debounced change dispatch to the server
// ---------------------------------------------------------------------------

let pendingChanges: DocumentChange[] = [];

const flushChanges = debounce(() => {
  if (pendingChanges.length === 0) {
    return;
  }
  const changes = pendingChanges;
  pendingChanges = [];
  void getRequestClient().sendDocumentTransaction({ changes });
}, 400);

function isScratchChange(change: DocumentChange): boolean {
  if ("cellId" in change && change.cellId === SCRATCH_CELL_ID) {
    return true;
  }
  return false;
}

function enqueue(change: DocumentChange) {
  if (store.get(kioskModeAtom)) {
    return;
  }
  // The scratchpad cell is local-only — don't sync it to the document.
  if (isScratchChange(change)) {
    return;
  }
  pendingChanges.push(change);
  flushChanges();
}

/**
 * Middleware for the notebook reducer. Converts actions to document changes
 * via toDocumentChanges and enqueues them for debounced dispatch.
 */
export function documentTransactionMiddleware(
  prevState: NotebookState,
  newState: NotebookState,
  action: CellAction,
): void {
  for (const change of toDocumentChanges(prevState, newState, action)) {
    enqueue(change);
  }
}

// ---------------------------------------------------------------------------
// Apply: dispatch incoming changes as reducer actions
// ---------------------------------------------------------------------------

/**
 * Apply document transaction changes to the frontend cell state.
 *
 * Each change is applied immediately and in order so that subsequent changes
 * see the state produced by earlier changes (e.g. move-cell after create-cell).
 */
export function applyTransactionChanges(
  changes: TransactionChange[],
  actions: CellActions,
  getCurrentCellIds: () => CellId[],
): void {
  const cancelled = cancelledCellIds(changes);

  // Process set-config changes after everything else. The tree must be fully
  // restructured (create-cell, delete-cell, reorder-cells, move-cell) before
  // we start applying column metadata, since the follow-up rebuildCellColumns
  // step interprets each cell's config.column against the *final* flat order.
  // Sorting is stable within each group.
  const sortedChanges: TransactionChange[] = [
    ...changes.filter((c) => c.type !== "set-config"),
    ...changes.filter((c) => c.type === "set-config"),
  ];

  // Track whether any change updated a cell's column, and remember the final
  // flat order produced by a reorder-cells change (if any). After all changes
  // are applied, these are used to rebuild the MultiColumn tree so that cells
  // physically move to the column their metadata says they belong in.
  let hasColumnChange = false;
  let reorderOrder: CellId[] | null = null;

  for (const change of sortedChanges) {
    if (
      cancelled.size > 0 &&
      "cellId" in change &&
      cancelled.has(change.cellId)
    ) {
      continue;
    }
    if (change.type === "set-config") {
      hasColumnChange = true;
    }
    if (change.type === "create-cell" && change.config?.column != null) {
      hasColumnChange = true;
    }
    if (change.type === "reorder-cells") {
      reorderOrder = change.cellIds as CellId[];
    }
    for (const action of fromDocumentChanges([change], getCurrentCellIds)) {
      // @ts-expect-error - TypeScript is not smart enough to know we have correctly mapped type -> payload
      actions[action.type](action.payload);
    }
  }

  if (hasColumnChange) {
    actions.rebuildCellColumns({
      cellIds: reorderOrder ?? getCurrentCellIds(),
    });
  }
}

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

export const exportedForTesting = {
  cancelPendingChanges: () => {
    flushChanges.cancel();
    pendingChanges = [];
  },
  drainChanges: (): DocumentChange[] => {
    flushChanges.cancel();
    const drained = pendingChanges;
    pendingChanges = [];
    return drained;
  },
};
