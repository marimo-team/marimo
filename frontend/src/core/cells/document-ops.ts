/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Document ops: the bridge between notebook reducer actions and the
 * document transaction wire format.
 *
 * Pure functions:
 * - toDocumentOps: reducer action + state diff → document ops
 * - fromDocumentOps: document ops → reducer actions
 * - cancelledCellIds: detect create+delete cancellations
 *
 * Impure wrappers (for use by the reducer middleware and websocket):
 * - documentTransactionMiddleware: debounces and sends ops to the server
 * - applyTransactionOps: dispatches actions from incoming ops
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
import type { CellData } from "./types";

export type DocumentOp = NotebookDocumentTransactionRequest["changes"][number];

type Transaction =
  NotificationMessageData<"notebook-document-transaction">["transaction"];
type TransactionOp = Transaction["changes"][number];

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
 * create-cell ops for each, with position derived from newState.
 */
function newCellOps(
  prevState: NotebookState,
  newState: NotebookState,
): DocumentOp[] {
  const prevIds = new Set(prevState.cellIds.inOrderIds);
  const ops: DocumentOp[] = [];
  for (const id of newState.cellIds.inOrderIds) {
    if (!prevIds.has(id)) {
      const cell = getCell(id, newState);
      if (cell) {
        ops.push({
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
  return ops;
}

/**
 * Find cells that were removed between prevState and newState and return
 * delete-cell ops for each.
 */
function deletedCellOps(
  prevState: NotebookState,
  newState: NotebookState,
): DocumentOp[] {
  const newIds = new Set(newState.cellIds.inOrderIds);
  const ops: DocumentOp[] = [];
  for (const id of prevState.cellIds.inOrderIds) {
    if (!newIds.has(id)) {
      ops.push({ type: "delete-cell", cellId: id });
    }
  }
  return ops;
}

/**
 * Produce set-config ops for cells whose column index changed between
 * prevState and newState, plus a reorder-cells op for the new ordering.
 */
function columnChangeOps(
  prevState: NotebookState,
  newState: NotebookState,
): DocumentOp[] {
  const prevColumns = columnIndexMap(prevState);
  const newColumns = columnIndexMap(newState);
  const ops: DocumentOp[] = [];

  for (const [cellId, newCol] of newColumns) {
    const prevCol = prevColumns.get(cellId);
    if (prevCol !== newCol) {
      ops.push({
        type: "set-config",
        cellId: cellId,
        column: newCol,
      });
    }
  }

  ops.push({
    type: "reorder-cells",
    cellIds: newState.cellIds.inOrderIds,
  });

  return ops;
}

// ---------------------------------------------------------------------------
// toDocumentOps: action + state → ops
// ---------------------------------------------------------------------------

/**
 * Given a reducer action and the before/after notebook state, return the
 * document ops that represent the change. Returns an empty array for
 * actions that don't affect document structure.
 */
export function toDocumentOps(
  prevState: NotebookState,
  newState: NotebookState,
  action: DispatchedActionOf<CellActions>,
): DocumentOp[] {
  switch (action.type) {
    // createNewCell → create-cell
    // Reads code, name, and config from the newly created cell in newState.
    // Position is derived from newState via anchorOf (after or before neighbor).
    case "createNewCell":
      return newCellOps(prevState, newState);

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

    // dropCellOverCell/dropCellOverColumn → set-config + reorder-cells
    // Drag-and-drop reorders can move cells within or across columns.
    // We emit config changes for cells whose column changed, then
    // the full ordering.
    case "dropCellOverCell":
    case "dropCellOverColumn":
      return columnChangeOps(prevState, newState);

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
    // Maps CellConfig's snake_case hide_code to the op's camelCase hideCode.
    // Only includes fields that were actually specified in the partial config
    // (from the action payload, not the full cell config).
    case "updateCellConfig": {
      const { cellId, config } = action.payload;
      return [
        {
          type: "set-config",
          cellId: cellId,
          ...(config.hide_code != null && { hideCode: config.hide_code }),
          ...(config.disabled != null && { disabled: config.disabled }),
          ...(config.column != null && { column: config.column }),
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
      return columnChangeOps(prevState, newState);

    // addColumn creates a new column with a new empty cell.
    // Emits create-cell for the new cell plus column layout ops.
    case "addColumn":
      return [
        ...newCellOps(prevState, newState),
        ...columnChangeOps(prevState, newState),
      ];

    // undoDeleteCell restores a deleted cell from history.
    case "undoDeleteCell": {
      const ops = newCellOps(prevState, newState);
      const colOps = columnChangeOps(prevState, newState);
      // Only include column ops if layout actually changed
      // (colOps always has at least a reorder-cells op)
      return colOps.length > 1 ? [...ops, ...colOps] : ops;
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
        ...newCellOps(prevState, newState),
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
        ...deletedCellOps(prevState, newState),
      ];
    }

    // moveToNextCell: may create a new cell at boundary.
    case "moveToNextCell":
      return newCellOps(prevState, newState);

    // addSetupCellIfDoesntExist: creates setup cell if missing.
    case "addSetupCellIfDoesntExist":
      return newCellOps(prevState, newState);

    // UI-only actions — no document ops.
    case "focusCell":
    case "focusTopCell":
    case "focusBottomCell":
    case "scrollToTarget":
    case "showCellIfHidden":
    case "markTouched":
    case "markUntouched":
      return [];

    // Kernel/runtime state — never produces document ops.
    case "prepareForRun":
    case "handleCellMessage":
    case "setCellIds":
    case "setCellCodes":
    case "setCells":
    case "setStdinResponse":
    case "clearSerializedEditorState":
    case "clearCellOutput":
    case "clearCellConsoleOutput":
    case "clearAllCellOutputs":
    case "clearLogs":
      return [];

    // Editor UI state — no document ops.
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
// fromDocumentOps: ops → actions
// ---------------------------------------------------------------------------

/**
 * Find cell IDs that are both created and deleted in a set of ops.
 * These cancel out and should be skipped.
 */
export function cancelledCellIds(ops: TransactionOp[]): Set<string> {
  const created = new Set<string>();
  const deleted = new Set<string>();
  for (const op of ops) {
    if (op.type === "create-cell") {
      created.add(op.cellId);
    } else if (op.type === "delete-cell") {
      deleted.add(op.cellId);
    }
  }
  return created.intersection(deleted);
}

/**
 * Given document ops (from the server) and the current cell ordering,
 * return the reducer actions that apply them to frontend state.
 */
export function fromDocumentOps(
  ops: TransactionOp[],
  getCurrentCellIds: () => CellId[],
): CellAction[] {
  const actions: CellAction[] = [];

  for (const op of ops) {
    switch (op.type) {
      // create-cell → createNewCell + updateCellName + updateCellConfig
      // Translates the op's before/after anchor into createNewCell's
      // cellId+before pair. The op carries code, name, and a full CellConfig.
      // createNewCell only accepts hideCode, so name and remaining config
      // (disabled, column) are applied as separate follow-up actions.
      case "create-cell": {
        let cellId: CellId | "__end__" = "__end__";
        let before = false;
        if (op.after) {
          cellId = op.after;
          before = false;
        } else if (op.before) {
          cellId = op.before;
          before = true;
        }
        actions.push({
          type: "createNewCell",
          payload: {
            cellId,
            before,
            code: op.code,
            newCellId: op.cellId as CellId,
            autoFocus: false,
            hideCode: op.config?.hide_code ?? false,
          },
        });
        if (op.name) {
          actions.push({
            type: "updateCellName",
            payload: { cellId: op.cellId as CellId, name: op.name },
          });
        }
        if (op.config?.disabled != null || op.config?.column != null) {
          actions.push({
            type: "updateCellConfig",
            payload: {
              cellId: op.cellId as CellId,
              config: {
                ...(op.config.disabled != null && {
                  disabled: op.config.disabled,
                }),
                ...(op.config.column != null && { column: op.config.column }),
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
          payload: { cellId: op.cellId as CellId },
        });
        break;

      // move-cell → setCellIds
      // Reconstructs the full ordering by splicing the cell out and
      // reinserting it relative to the before/after anchor. Falls back
      // to appending (after) or prepending (before) if the anchor is
      // missing. No-ops if the cell itself doesn't exist.
      case "move-cell": {
        const ids = [...getCurrentCellIds()];
        const cellId = op.cellId as CellId;
        const idx = ids.indexOf(cellId);
        if (idx < 0) {
          break;
        }
        ids.splice(idx, 1);
        if (op.after) {
          const afterIdx = ids.indexOf(op.after);
          if (afterIdx >= 0) {
            ids.splice(afterIdx + 1, 0, cellId);
          } else {
            ids.push(cellId);
          }
        } else if (op.before) {
          const beforeIdx = ids.indexOf(op.before);
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
      // bulk reorder ops where expressing individual moves is impractical.
      case "reorder-cells":
        actions.push({
          type: "setCellIds",
          payload: { cellIds: op.cellIds as CellId[] },
        });
        break;

      // set-code → setCellCodes
      // Marks the code as stale (codeIsStale: true) since it came from
      // an external source and hasn't been executed yet.
      case "set-code":
        actions.push({
          type: "setCellCodes",
          payload: {
            ids: [op.cellId as CellId],
            codes: [op.code],
            codeIsStale: true,
          },
        });
        break;

      // set-name → updateCellName
      // Direct 1:1 mapping.
      case "set-name":
        actions.push({
          type: "updateCellName",
          payload: { cellId: op.cellId as CellId, name: op.name },
        });
        break;

      // set-config → updateCellConfig
      // Maps the op's camelCase hideCode back to CellConfig's snake_case
      // hide_code. Only includes fields that are non-null (null means
      // "not specified" on the wire, not "clear the value").
      case "set-config":
        actions.push({
          type: "updateCellConfig",
          payload: {
            cellId: op.cellId as CellId,
            config: {
              ...(op.hideCode != null && { hide_code: op.hideCode }),
              ...(op.disabled != null && { disabled: op.disabled }),
              ...(op.column != null && { column: op.column }),
            },
          },
        });
        break;
    }
  }

  return actions;
}

// ---------------------------------------------------------------------------
// Middleware: debounced op dispatch to the server
// ---------------------------------------------------------------------------

let pendingChanges: DocumentOp[] = [];

const flushOps = debounce(() => {
  if (pendingChanges.length === 0) {
    return;
  }
  const changes = pendingChanges;
  pendingChanges = [];
  void getRequestClient().sendDocumentTransaction({ changes });
}, 400);

function enqueue(op: DocumentOp) {
  if (store.get(kioskModeAtom)) {
    return;
  }
  pendingChanges.push(op);
  flushOps();
}

/**
 * Middleware for the notebook reducer. Converts actions to document ops
 * via toDocumentOps and enqueues them for debounced dispatch.
 */
export function documentTransactionMiddleware(
  prevState: NotebookState,
  newState: NotebookState,
  action: CellAction,
): void {
  for (const op of toDocumentOps(prevState, newState, action)) {
    enqueue(op);
  }
}

// ---------------------------------------------------------------------------
// Apply: dispatch incoming ops as reducer actions
// ---------------------------------------------------------------------------

/**
 * Apply document transaction ops to the frontend cell state.
 *
 * Each op is applied immediately and in order so that subsequent ops
 * see the state produced by earlier ops (e.g. move-cell after create-cell).
 */
export function applyTransactionOps(
  ops: TransactionOp[],
  actions: CellActions,
  getCurrentCellIds: () => CellId[],
): void {
  const cancelled = cancelledCellIds(ops);

  for (const op of ops) {
    if (cancelled.size > 0 && "cellId" in op && cancelled.has(op.cellId)) {
      continue;
    }
    for (const action of fromDocumentOps([op], getCurrentCellIds)) {
      // @ts-expect-error - TypeScript is not smart enough to know we have correctly mapped type -> payload
      actions[action.type](action.payload);
    }
  }
}

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

export const exportedForTesting = {
  cancelPendingOps: () => {
    flushOps.cancel();
    pendingChanges = [];
  },
  drainOps: (): DocumentOp[] => {
    flushOps.cancel();
    const ops = pendingChanges;
    pendingChanges = [];
    return ops;
  },
};
