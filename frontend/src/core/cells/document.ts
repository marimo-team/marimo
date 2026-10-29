/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Keep the notebook state and the host document in step while cells live
 * in both.
 *
 * TODO(MO-8028): Delete this module once components read cells from the
 * document model and `notebookAtom` holds only runtime and editor state.
 */

import type * as Protocol from "@marimo-team/client/protocol";
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
import { CollapsibleTree, MultiColumn } from "@/utils/id-tree";
import { prepareCellCodeUpdate } from "../codemirror/language/cell-code";
import type { CellConfig } from "../network/types";
import { canUseRtc, isRtcEnabled } from "../rtc/state";
import { store } from "../state/jotai";
import { activeDocumentModelAtom } from "../session/active-notebook";
import type { CellActions, NotebookState } from "./cells";
import { groupByColumn } from "./columns";
import type { CellId } from "./ids";
import {
  type CellData,
  createCell,
  createCellConfig,
  createCellRuntimeState,
  isEdited,
} from "./types";

type CellAction = DispatchedActionOf<CellActions>;

// Following the document ----------------------------------------------------

/** Rebuild the tree for `columns`, keeping column ids and collapsed sections. */
function reconcileColumns(
  current: MultiColumn<CellId>,
  columns: CellId[][],
): MultiColumn<CellId> {
  const previous = current.getColumns();
  // The document cannot hold an empty column, so keep the ones this client has.
  while (previous[columns.length]?.length === 0) {
    columns.push([]);
  }
  if (
    columns.length === previous.length &&
    columns.every((ids, index) => isEqual(ids, previous[index].inOrderIds))
  ) {
    return current;
  }
  return new MultiColumn(
    columns.map((ids, index) =>
      CollapsibleTree.fromWithPreviousShape(ids, previous[index]),
    ),
  );
}

/** The cell's data with the document's fields, and its editor brought along. */
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
  const cellIds = reconcileColumns(state.cellIds, groupByColumn(document));
  let { cellData, cellRuntime, cellHandles } = state;
  for (const id of cellIds.inOrderIds) {
    const cell = document.cells.get(id);
    const current = state.cellData[id];
    if (cell === undefined) {
      continue;
    }
    if (current === undefined) {
      // A new cell has no run to be edited from.
      cellData = {
        ...cellData,
        [id]: createCell({
          id,
          code: cell.code ?? "",
          name: cell.name,
          config: createCellConfig(cell.config),
        }),
      };
      cellRuntime = { ...cellRuntime, [id]: createCellRuntimeState() };
      cellHandles = { ...cellHandles, [id]: createRef() };
      continue;
    }
    const next = followCell(current, cell, state.cellHandles[id]);
    if (next !== current) {
      cellData = { ...cellData, [id]: next };
    }
  }
  const present = new Set(cellIds.inOrderIds);
  const removed = state.cellIds.inOrderIds.filter((id) => !present.has(id));
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

const CONFIG_FIELDS = ["disabled", "hide_code", "expand_output"] as const;

/** The fields of `after` that differ from `before`, leaving `column` to the tree. */
function configPatch(
  before: CellConfig,
  after: CellConfig,
): Partial<Protocol.CellConfig> | null {
  const patch: Partial<Protocol.CellConfig> = {};
  for (const field of CONFIG_FIELDS) {
    if (before[field] !== after[field]) {
      patch[field] = after[field] ?? false;
    }
  }
  return Object.keys(patch).length === 0 ? null : patch;
}

/**
 * The `column` configs that make the document's columns match the tree's.
 *
 * A cell without a column follows the cell before it, so only cells whose
 * resolved column differs from their position need one.
 */
function columnFixes(state: NotebookState): Array<[CellId, number | null]> {
  const fixes: Array<[CellId, number | null]> = [];
  const columns = state.cellIds.getColumns();
  if (columns.length === 1) {
    for (const id of columns[0].inOrderIds) {
      const column = state.cellData[id].config.column;
      if (column != null && column !== 0) {
        fixes.push([id, null]);
      }
    }
    return fixes;
  }
  let inherited = 0;
  columns.forEach((column, target) => {
    for (const id of column.inOrderIds) {
      const configured = state.cellData[id].config.column;
      const resolved =
        configured != null && configured >= 0 ? configured : inherited;
      if (resolved !== target) {
        fixes.push([id, target]);
      }
      inherited = target;
    }
  });
  return fixes;
}

/** The edit that makes the document match `next`, or null when it already does. */
function diffNotebook(
  prev: NotebookState,
  next: NotebookState,
): DocumentEdit | null {
  const steps: Array<(tx: DocumentEditor) => void> = [];
  const prevOrder = prev.cellIds.inOrderIds;
  const nextOrder = next.cellIds.inOrderIds;
  const prevIds = new Set(prevOrder);
  const nextIds = new Set(nextOrder);
  for (const id of prevOrder) {
    if (!nextIds.has(id)) {
      steps.push((tx) => tx.deleteCell(id));
    }
  }
  const created: CellId[] = [];
  for (const id of nextOrder) {
    const cell = next.cellData[id];
    const before = prev.cellData[id];
    if (!prevIds.has(id) || before === undefined) {
      created.push(id);
      steps.push((tx) =>
        tx.createCell({
          id,
          code: cell.code,
          name: cell.name,
          config: cell.config,
        }),
      );
      continue;
    }
    if (before === cell) {
      continue;
    }
    if (before.code !== cell.code) {
      steps.push((tx) => tx.setCode(id, cell.code));
    }
    if (before.name !== cell.name) {
      steps.push((tx) => tx.setName(id, cell.name));
    }
    const patch = configPatch(before.config, cell.config);
    if (patch !== null) {
      steps.push((tx) => tx.updateConfig(id, patch));
    }
  }
  for (const [id, column] of columnFixes(next)) {
    steps.push((tx) => tx.updateConfig(id, { column }));
  }
  // Created cells go to the end, so the order is set when they belong elsewhere.
  const survivors = prevOrder.filter((id) => nextIds.has(id));
  if (!isEqual(nextOrder, [...survivors, ...created])) {
    steps.push((tx) => tx.setOrder(nextOrder));
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
 * TODO(MO-8028): Each action family that moves onto the model removes its
 * part of `diffNotebook`. The middleware goes with the last one, code.
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

/**
 * Run a legacy save after this client's edits reach the host. The save
 * carries the whole notebook, so when the edits cannot be sent it still
 * runs, and the model resumes against the saved document.
 */
export async function withDocumentSave<T>(save: () => Promise<T>): Promise<T> {
  const model = store.get(activeDocumentModelAtom);
  if (model === null) {
    return save();
  }
  let flushed = true;
  try {
    await model.flush();
  } catch {
    flushed = false;
  }
  const result = await save();
  if (!flushed) {
    void model.retry().catch(() => undefined);
  }
  return result;
}
