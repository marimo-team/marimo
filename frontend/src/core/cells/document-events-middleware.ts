/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Middleware that maps notebook reducer actions to document events
 * and sends them to POST /api/document/events.
 *
 * The middleware watches for actions that modify document structure
 * (cell ordering, code, names, configs) and queues corresponding
 * events. Events are flushed to the server on a debounce.
 */

import { debounce } from "lodash-es";
import type { CellId } from "./ids";
import type { NotebookState } from "./cells";
import { kioskModeAtom } from "../mode";
import { getRequestClient } from "../network/requests";
import type { DocumentEventsRequest } from "../network/types";
import { store } from "../state/jotai";

type DocumentEvent = DocumentEventsRequest["events"][number];

let pendingEvents: DocumentEvent[] = [];

const flushEvents = debounce(() => {
  if (pendingEvents.length === 0) {
    return;
  }
  const events = pendingEvents;
  pendingEvents = [];
  void getRequestClient().sendDocumentEvents({ events });
}, 400);

function enqueue(event: DocumentEvent) {
  if (store.get(kioskModeAtom)) {
    return;
  }
  pendingEvents.push(event);
  flushEvents();
}

/**
 * Find which cell ID is immediately before `cellId` in the new state,
 * or null if it's first.
 */
function findAfter(state: NotebookState, cellId: CellId): CellId | null {
  const ids = state.cellIds.inOrderIds;
  const idx = ids.indexOf(cellId);
  return idx > 0 ? ids[idx - 1] : null;
}

/**
 * Middleware for the notebook reducer. Intercepts actions that modify
 * document structure and queues document events.
 */
export function documentEventsMiddleware(
  _prevState: NotebookState,
  newState: NotebookState,
  action: { type: string; payload: unknown },
): void {
  const p = action.payload as Record<string, unknown>;

  switch (action.type) {
    case "createNewCell": {
      const cellId = p.cellId as CellId;
      const cell = newState.cellData[cellId];
      if (cell) {
        enqueue({
          type: "cell-created",
          id: cellId,
          code: cell.code,
          name: cell.name,
          after: findAfter(newState, cellId),
        });
      }
      break;
    }

    case "deleteCell": {
      enqueue({
        type: "cell-deleted",
        id: p.cellId as string,
      });
      break;
    }

    case "moveCell":
    case "dropCellOverCell":
    case "dropCellOverColumn":
    case "sendToTop":
    case "sendToBottom": {
      const cellId = p.cellId as CellId;
      enqueue({
        type: "cell-moved",
        id: cellId,
        after: findAfter(newState, cellId),
      });
      break;
    }

    case "updateCellCode": {
      enqueue({
        type: "code-changed",
        id: p.cellId as string,
        code: p.code as string,
      });
      break;
    }

    case "updateCellName": {
      enqueue({
        type: "name-changed",
        id: p.cellId as string,
        name: p.name as string,
      });
      break;
    }

    // No default — most actions don't map to document events.
  }
}
