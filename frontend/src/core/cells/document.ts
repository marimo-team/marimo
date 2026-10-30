/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Make the notebook state follow the host document while cells live in
 * both. Edits go the other way through the document model directly: the
 * cell operations write it, and each cell editor is bound to its cell.
 *
 * TODO(MO-8028): Delete this module once components read cells from the
 * document model and `notebookAtom` holds only runtime and editor state.
 */

import { dequal as isEqual } from "dequal";
import type { createStore } from "jotai";
import { createRef } from "react";
import type {
  DocumentModel,
  EditableCell,
  EditableDocument,
} from "@/core/notebook/document";
import { store } from "../state/jotai";
import { activeDocumentModelAtom } from "../session/active-notebook";
import type { NotebookState } from "./cells";
import type { CellId } from "./ids";
import {
  type CellData,
  createCell,
  createCellConfig,
  createCellRuntimeState,
  isEdited,
} from "./types";

// Following the document ----------------------------------------------------

/** The cell's data after the document's cell, the same object when nothing differs. */
function followCell(current: CellData, cell: EditableCell): CellData {
  // Withheld source keeps the code this client has.
  const code = cell.code ?? current.code;
  const config = isEqual(current.config, cell.config)
    ? current.config
    : createCellConfig(cell.config);
  if (
    code === current.code &&
    cell.name === current.name &&
    config === current.config
  ) {
    return current;
  }
  if (code === current.code) {
    return { ...current, name: cell.name, config };
  }
  return {
    ...current,
    code,
    name: cell.name,
    config,
    edited: isEdited(current.lastCodeRun, code),
  };
}

/**
 * Make the notebook's cells and order follow the document.
 *
 * Returns the same state when nothing differs, so a local edit that the
 * document already reflects changes nothing.
 *
 * TODO(MO-8028): Delete with `reconcileDocument` once cells are read from
 * the document model.
 */
export function applyDocument(
  state: NotebookState,
  document: EditableDocument,
): NotebookState {
  // The protocol's ids are plain strings; the notebook brands them.
  const cellIds = isEqual(document.order, state.cellIds)
    ? state.cellIds
    : ([...document.order] as CellId[]);
  let { cellData, cellRuntime, cellHandles } = state;
  for (const id of cellIds) {
    const cell = document.cells.get(id);
    const current = state.cellData[id];
    if (cell === undefined) {
      continue;
    }
    if (current === undefined) {
      // A new cell with code is stale until it runs. The kernel's last run
      // settles it on kernel-ready.
      const code = cell.code ?? "";
      cellData = {
        ...cellData,
        [id]: createCell({
          id,
          code,
          name: cell.name,
          config: createCellConfig(cell.config),
          edited: code.trim().length > 0,
        }),
      };
      cellRuntime = {
        ...cellRuntime,
        [id]: cellRuntime[id] ?? createCellRuntimeState(),
      };
      cellHandles = { ...cellHandles, [id]: createRef() };
      continue;
    }
    const next = followCell(current, cell);
    if (next !== current) {
      cellData = { ...cellData, [id]: next };
    }
  }
  const present = new Set(cellIds);
  const removed = state.cellIds.filter((id) => !present.has(id));
  if (removed.length > 0) {
    const gone = new Set(removed);
    const keep = <V>(record: Record<CellId, V>): Record<CellId, V> =>
      Object.fromEntries(
        Object.entries(record).filter(([id]) => !gone.has(id as CellId)),
      ) as Record<CellId, V>;
    cellData = keep(cellData);
    cellRuntime = keep(cellRuntime);
    cellHandles = keep(cellHandles);
  }
  if (
    cellIds === state.cellIds &&
    cellData === state.cellData &&
    removed.length === 0
  ) {
    return state;
  }
  return { ...state, cellIds, cellData, cellRuntime, cellHandles };
}

/**
 * Reconcile the model's document now and on each change, until the signal aborts.
 *
 * TODO(MO-8028): Delete with `applyDocument`.
 */
export function followDocument({
  store,
  model,
  reconcile,
  signal,
}: {
  store: ReturnType<typeof createStore>;
  model: Pick<DocumentModel, "documentAtom">;
  reconcile: (document: EditableDocument) => void;
  signal: AbortSignal;
}): void {
  const follow = () => {
    const document = store.get(model.documentAtom);
    if (document !== null) {
      reconcile(document);
    }
  };
  const unsubscribe = store.sub(model.documentAtom, follow);
  signal.addEventListener("abort", unsubscribe, { once: true });
  follow();
}

// Commands that read the document on the host -------------------------------

/** Send this client's edits to the host before a command that reads them there. */
export async function flushDocument(): Promise<void> {
  const model = store.get(activeDocumentModelAtom);
  if (model !== null) {
    await model.flush();
  }
}
