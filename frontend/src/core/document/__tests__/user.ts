/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import type { createStore } from "jotai/vanilla";
import type { DocumentModel } from "../model";

/** Translate user actions and observations without keeping any expected state. */
export function createUser(
  store: ReturnType<typeof createStore>,
  model: DocumentModel,
) {
  function observe(promise: Promise<Protocol.Document>) {
    // A failed assertion may end a scenario before it awaits sync; teardown
    // should not obscure that failure with an unhandled abort rejection.
    void promise.catch(() => undefined);
    return promise;
  }
  return {
    changeCode(id: Protocol.CellId, code: string) {
      store.set(model.editAtom, (tx) => tx.setCode(id, code));
    },
    changeCells(
      changes: Record<Protocol.CellId, Partial<Omit<Protocol.CellInput, "id">>>,
    ) {
      store.set(model.editAtom, (tx) => {
        for (const [id, patch] of Object.entries(changes)) {
          if (patch.code !== undefined) {tx.setCode(id, patch.code);}
          if (patch.name !== undefined) {tx.setName(id, patch.name);}
          if (patch.config !== undefined) {tx.updateConfig(id, patch.config);}
        }
      });
    },
    createCell(cell: Protocol.CellInput) {
      store.set(model.editAtom, (tx) => tx.createCell(cell));
    },
    deleteCell(id: Protocol.CellId) {
      store.set(model.editAtom, (tx) => tx.deleteCell(id));
    },
    cell(id: Protocol.CellId) {
      const cell = store.get(model.cellAtom(id));
      return cell === undefined
        ? undefined
        : {
            id: cell.id,
            code: cell.code,
            name: cell.name,
            config: cell.config,
          };
    },
    order: () => store.get(model.orderAtom),
    status: () => store.get(model.syncStateAtom),
    sync: () => observe(model.flush()),
    retry: () => observe(model.retry()),
  };
}
