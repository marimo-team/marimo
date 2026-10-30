/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Keep the notebook state and the host document in step while cells live
 * in both.
 *
 * TODO(MO-8028): Delete this module once components read cells from the
 * document model and `notebookAtom` holds only runtime and editor state.
 */

import { dequal as isEqual } from "dequal";
import type { createStore } from "jotai";
import { createRef, type RefObject } from "react";
import type { CellHandle } from "@/components/editor/notebook-cell";
import type {
  DocumentEdit,
  DocumentEditor,
  DocumentModel,
  EditableCell,
  EditableDocument,
} from "@/core/notebook/document";
import type { DispatchedActionOf } from "@/utils/createReducer";
import { prepareCellCodeUpdate } from "../codemirror/language/cell-code";
import { canUseRtc, isRtcEnabled } from "../rtc/state";
import { store } from "../state/jotai";
import { activeDocumentModelAtom } from "../session/active-notebook";
import type { NotebookState, ReducerCellActions } from "./cells";
import type { CellId } from "./ids";
import {
  type CellData,
  createCell,
  createCellConfig,
  createCellRuntimeState,
  isEdited,
} from "./types";

type CellAction = DispatchedActionOf<ReducerCellActions>;

// Following the document ----------------------------------------------------

/** Rebuild the tree for `columns`, keeping column ids. */
function followCell(
  current: CellData,
  cell: EditableCell,
  handle: RefObject<CellHandle | null> | undefined,
): CellData {
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
  // RTC cells follow Loro. Other editors take the host's code; one that
  // shows it already, as the editor this client types in does, is left alone.
  if (!isRtcEnabled() || !canUseRtc(current.id)) {
    const view = handle?.current?.editorViewOrNull;
    const update = view && prepareCellCodeUpdate(view.state, code);
    if (update) {
      view.dispatch(update);
    }
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
    const next = followCell(current, cell, state.cellHandles[id]);
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

// Editing the document ------------------------------------------------------

/**
 * The edit that writes the code a reducer action changed, or null when none
 * did. Order, creation, deletion, names and configs are edited on the model
 * directly by their atoms.
 */
function diffNotebook(
  prev: NotebookState,
  next: NotebookState,
): DocumentEdit | null {
  const steps: Array<(tx: DocumentEditor) => void> = [];
  for (const id of next.cellIds) {
    const cell = next.cellData[id];
    const before = prev.cellData[id];
    if (before !== undefined && cell !== before && before.code !== cell.code) {
      steps.push((tx) => tx.setCode(id, cell.code));
    }
  }
  if (steps.length === 0) {
    return null;
  }
  return (tx) => {
    for (const step of steps) {
      step(tx);
    }
  };
}

/**
 * Middleware for the notebook reducer. Writes what an action changed about
 * the cells and their order into the document model as one edit.
 *
 * TODO(MO-8028): Only code is left in `diffNotebook`. The middleware goes
 * with it, once the editors bind to the model.
 */
export function documentEditMiddleware(
  prev: NotebookState,
  next: NotebookState,
  action: CellAction,
): void {
  // The document replaces the notebook's cells, so following it is no edit.
  if (action.type === "reconcileDocument") {
    return;
  }
  if (prev.cellIds === next.cellIds && prev.cellData === next.cellData) {
    return;
  }
  const model = store.get(activeDocumentModelAtom);
  if (model === null) {
    return;
  }
  const edit = diffNotebook(prev, next);
  if (edit !== null) {
    store.set(model.editAtom, edit);
  }
}

// Commands that read the document on the host -------------------------------

/** Send this client's edits to the host before a command that reads them there. */
export async function flushDocument(): Promise<void> {
  const model = store.get(activeDocumentModelAtom);
  if (model !== null) {
    await model.flush();
  }
}
