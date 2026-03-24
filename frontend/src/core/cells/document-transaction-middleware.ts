/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Middleware that maps notebook reducer actions to document ops
 * and sends them to POST /api/document/transaction.
 *
 * The middleware watches for actions that modify document structure
 * (cell ordering, code, names, configs) and queues corresponding
 * ops. Ops are debounced and flushed as a single transaction.
 */

import { debounce } from "lodash-es";
import type { DispatchedActionOf } from "@/utils/createReducer";
import { kioskModeAtom } from "../mode";
import { getRequestClient } from "../network/requests";
import type { NotebookDocumentTransactionRequest } from "../network/types";
import { store } from "../state/jotai";
import type { CellActions, NotebookState } from "./cells";

type DocumentOp = NotebookDocumentTransactionRequest["ops"][number];

let pendingOps: DocumentOp[] = [];

const flushOps = debounce(() => {
  if (pendingOps.length === 0) {
    return;
  }
  const ops = pendingOps;
  pendingOps = [];
  void getRequestClient().sendDocumentTransaction({ ops });
}, 400);

function enqueue(op: DocumentOp) {
  if (store.get(kioskModeAtom)) {
    return;
  }
  pendingOps.push(op);
  flushOps();
}

/**
 * Middleware for the notebook reducer. Intercepts actions that modify
 * document structure and queues document ops.
 */
export function documentTransactionMiddleware(
  _prevState: NotebookState,
  newState: NotebookState,
  action: DispatchedActionOf<CellActions>,
): void {
  switch (action.type) {
    case "createNewCell": {
      const { cellId } = action.payload;
      const cell = newState.cellData[cellId];
      if (cell) {
        const ids = newState.cellIds.inOrderIds;
        const idx = ids.indexOf(cellId);
        enqueue({
          type: "create-cell",
          cellId: cellId,
          code: cell.code,
          name: cell.name,
          config: {},
          after: idx > 0 ? ids[idx - 1] : null,
        });
      }
      break;
    }

    case "deleteCell": {
      const { cellId } = action.payload;
      enqueue({
        type: "delete-cell",
        cellId: cellId,
      });
      break;
    }

    case "moveCell":
    case "sendToTop":
    case "sendToBottom": {
      const { cellId } = action.payload;
      const ids = newState.cellIds.inOrderIds;
      const idx = ids.indexOf(cellId);
      enqueue({
        type: "move-cell",
        cellId: cellId,
        after: idx > 0 ? ids[idx - 1] : null,
      });
      break;
    }

    // Bulk reorders — send the full ordering
    case "dropCellOverCell":
    case "dropCellOverColumn": {
      enqueue({
        type: "reorder-cells",
        cellIds: newState.cellIds.inOrderIds,
      });
      break;
    }

    case "updateCellCode": {
      const { cellId, code } = action.payload;
      enqueue({
        type: "set-code",
        cellId: cellId,
        code: code,
      });
      break;
    }

    case "updateCellName": {
      const { cellId, name } = action.payload;
      enqueue({
        type: "set-name",
        cellId: cellId,
        name: name,
      });
      break;
    }

    // No default — most actions don't map to document ops.
  }
}

export const exportedForTesting = {
  cancelPendingOps: () => {
    flushOps.cancel();
    pendingOps = [];
  },
};
