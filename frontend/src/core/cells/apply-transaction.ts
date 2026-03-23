/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Apply document transaction ops to the frontend cell state.
 *
 * Each op is applied immediately and in order — no batching or
 * deferral. This avoids ordering bugs where e.g. a move-cell
 * references a cell that was just created in the same transaction.
 */

import type { NotificationMessageData } from "../kernel/messages";
import type { CellConfig } from "../network/types";
import type { CellId } from "./ids";

type Transaction =
  NotificationMessageData<"notebook-document-transaction">["transaction"];
type TransactionOp = Transaction["ops"][number];

interface CellActions {
  createNewCell: (action: {
    cellId: CellId | "__end__";
    before: boolean;
    code?: string;
    newCellId?: CellId;
    hideCode?: boolean;
    autoFocus?: boolean;
  }) => void;
  deleteCell: (action: { cellId: CellId }) => void;
  setCellIds: (action: { cellIds: CellId[] }) => void;
  setCellCodes: (action: {
    ids: CellId[];
    codes: string[];
    codeIsStale: boolean;
  }) => void;
  updateCellName: (action: { cellId: CellId; name: string }) => void;
  updateCellConfig: (action: {
    cellId: CellId;
    config: Partial<CellConfig>;
  }) => void;
}

export function applyTransactionOps(
  ops: TransactionOp[],
  actions: CellActions,
  getCurrentCellIds: () => CellId[],
): void {
  // Find cells that are both created and deleted in this transaction.
  // These cancel out and applying them would crash (the reducer tries
  // to serialize the editor state of a cell that hasn't rendered yet).
  const created = new Set<string>();
  const deleted = new Set<string>();
  for (const op of ops) {
    if (op.type === "create-cell") {
      created.add(op.cellId);
    } else if (op.type === "delete-cell") {
      deleted.add(op.cellId);
    }
  }
  const cancelledIds = created.intersection(deleted);

  for (const op of ops) {
    // Skip ops targeting cells that are both created and deleted.
    if (
      cancelledIds.size > 0 &&
      "cellId" in op &&
      cancelledIds.has(op.cellId)
    ) {
      continue;
    }
    switch (op.type) {
      case "create-cell": {
        // Determine the anchor cell and insertion direction.
        // `after` means insert after that cell (before=false).
        // `before` means insert before that cell (before=true).
        // Neither means append at the end.
        let cellId: CellId | "__end__" = "__end__";
        let before = false;
        if (op.after) {
          cellId = op.after as CellId;
          before = false;
        } else if (op.before) {
          cellId = op.before as CellId;
          before = true;
        }
        actions.createNewCell({
          cellId,
          before,
          code: op.code,
          newCellId: op.cellId as CellId,
          autoFocus: false,
          hideCode: op.config?.hide_code ?? false,
        });
        // Apply name if non-default
        if (op.name) {
          actions.updateCellName({
            cellId: op.cellId as CellId,
            name: op.name,
          });
        }
        break;
      }
      case "delete-cell":
        actions.deleteCell({ cellId: op.cellId as CellId });
        break;
      case "move-cell": {
        const ids = [...getCurrentCellIds()];
        const cellId = op.cellId as CellId;
        const idx = ids.indexOf(cellId);
        if (idx >= 0) {
          ids.splice(idx, 1);
          if (op.after) {
            const afterIdx = ids.indexOf(op.after as CellId);
            ids.splice(afterIdx + 1, 0, cellId);
          } else if (op.before) {
            const beforeIdx = ids.indexOf(op.before as CellId);
            ids.splice(beforeIdx, 0, cellId);
          }
          actions.setCellIds({ cellIds: ids });
        }
        break;
      }
      case "reorder-cells":
        actions.setCellIds({ cellIds: op.cellIds as CellId[] });
        break;
      case "set-code":
        actions.setCellCodes({
          ids: [op.cellId as CellId],
          codes: [op.code],
          codeIsStale: true,
        });
        break;
      case "set-name":
        actions.updateCellName({
          cellId: op.cellId as CellId,
          name: op.name,
        });
        break;
      case "set-config":
        actions.updateCellConfig({
          cellId: op.cellId as CellId,
          config: {
            ...(op.hideCode != null && { hide_code: op.hideCode }),
            ...(op.disabled != null && { disabled: op.disabled }),
            ...(op.column != null && { column: op.column }),
          },
        });
        break;
    }
  }
}
