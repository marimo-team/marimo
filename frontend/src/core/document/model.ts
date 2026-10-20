/* Copyright 2026 Marimo. All rights reserved. */

import { dequal } from "dequal";
import {
  atom,
  type Atom,
  type createStore,
  type WritableAtom,
} from "jotai/vanilla";
import { selectAtom } from "jotai/vanilla/utils";
import type { Document } from "../host/resources/document";
import * as Protocol from "@marimo-team/client/protocol";
import {
  type CellEdit,
  createCell,
  deleteCell,
  type Draft,
  type EditableCell,
  type EditableDocument,
  editCell,
  EMPTY_DRAFT,
  isEmptyDraft,
  type Placement,
  prune,
  sameCell,
  setOrder,
  toChanges,
  viewDocument,
} from "./draft";

/** Operations on a working draft, valid only during the edit callback. */
export interface DocumentEditor {
  setCode(id: Protocol.CellId, code: string): void;
  setName(id: Protocol.CellId, name: string): void;
  updateConfig(id: Protocol.CellId, patch: Partial<Protocol.CellConfig>): void;
  createCell(cell: Protocol.CellInput, placement?: Placement): void;
  deleteCell(id: Protocol.CellId): void;
  /** A permutation of the cells present at this point in the transaction. */
  setOrder(order: readonly Protocol.CellId[]): void;
}

/** Synchronous; a thrown error discards the entire transaction. */
export type DocumentEdit = (editor: DocumentEditor) => void;

interface ModelState {
  readonly confirmed: Document | null;
  readonly drafts: ReadonlyMap<Protocol.NotebookId, Draft>;
}

/** Local edits over confirmed host state, retained per notebook across snapshots. */
interface DocumentModel {
  /** Hold onto the selector; its value is stable until the cell changes. */
  cellAtom(id: Protocol.CellId): Atom<EditableCell | undefined>;
  readonly orderAtom: Atom<readonly Protocol.CellId[] | null>;
  readonly appConfigAtom: Atom<Readonly<
    Protocol.Document["app_config"]
  > | null>;
  /** Null when the document or source needed by a put is unavailable. */
  readonly changesAtom: Atom<readonly Protocol.Change[] | null>;
  readonly editAtom: WritableAtom<null, [edit: DocumentEdit], void>;
  /** Stop observing the source and accepting edits. Safe to repeat. */
  dispose(): void;
}

function draftOf(state: ModelState): Draft {
  return state.confirmed === null
    ? EMPTY_DRAFT
    : (state.drafts.get(state.confirmed.revision.notebook_id) ?? EMPTY_DRAFT);
}

function withDraft(state: ModelState, draft: Draft): ModelState {
  if (state.confirmed === null || draft === draftOf(state)) {
    return state;
  }
  const drafts = new Map(state.drafts);
  const notebookId = state.confirmed.revision.notebook_id;
  if (isEmptyDraft(draft)) {
    drafts.delete(notebookId);
  } else {
    drafts.set(notebookId, draft);
  }
  return { ...state, drafts };
}

/** Discard removed-cell edits when publishing a confirmed document. */
function reconcile(state: ModelState): ModelState {
  const { confirmed } = state;
  if (confirmed === null) {
    return state;
  }
  return withDraft(state, prune(confirmed, draftOf(state)));
}

/** Create once per source and store; the owner must dispose the model. */
export function createDocumentModel(
  store: ReturnType<typeof createStore>,
  source: Atom<Document | null>,
): DocumentModel {
  const stateAtom = atom<ModelState>({
    confirmed: store.get(source),
    drafts: new Map(),
  });
  let disposed = false;
  const documentAtom = atom((get): EditableDocument | null => {
    const state = get(stateAtom);
    return state.confirmed === null
      ? null
      : viewDocument(state.confirmed, draftOf(state));
  });
  const cellAtom = (id: Protocol.CellId) =>
    selectAtom(
      documentAtom,
      (document) => document?.cells.get(id),
      (a, b) =>
        a === b || (a !== undefined && b !== undefined && sameCell(a, b)),
    );
  const orderAtom = selectAtom(
    documentAtom,
    (document) => document?.order ?? null,
    dequal,
  );
  const appConfigAtom = selectAtom(
    stateAtom,
    (state) => state.confirmed?.revision.app_config ?? null,
    dequal,
  );
  const changesAtom = atom((get): readonly Protocol.Change[] | null => {
    const state = get(stateAtom);
    return state.confirmed === null
      ? null
      : toChanges(state.confirmed, draftOf(state));
  });

  const unsubscribe = store.sub(source, () => {
    const confirmed = store.get(source);
    store.set(stateAtom, (state) =>
      reconcile({
        ...state,
        confirmed,
      }),
    );
  });

  let editing = false;
  const editAtom = atom(null, (get, set, edit: DocumentEdit) => {
    if (editing) {
      throw new Error("Document transactions cannot be nested");
    }
    const state = get(stateAtom);
    if (disposed || state.confirmed === null) {
      return;
    }
    editing = true;
    try {
      const draft = editDocument(state.confirmed, draftOf(state), edit);
      if (
        disposed ||
        get(stateAtom) !== state ||
        get(source) !== state.confirmed
      ) {
        throw new Error("The document changed during the transaction");
      }
      set(stateAtom, withDraft(state, draft));
    } finally {
      editing = false;
    }
  });

  return {
    cellAtom,
    orderAtom,
    appConfigAtom,
    changesAtom,
    editAtom,
    dispose() {
      if (!disposed) {
        disposed = true;
        unsubscribe();
        store.set(stateAtom, {
          confirmed: null,
          drafts: new Map(),
        });
      }
    },
  };
}

function editDocument(
  confirmed: Document,
  draft: Draft,
  edit: DocumentEdit,
): Draft {
  let next = draft;
  let active = true;

  function assertActive() {
    if (!active) {
      throw new Error("The document transaction has ended");
    }
  }

  function hasCell(id: Protocol.CellId): boolean {
    const local = next.cells.get(id);
    return (
      local?.kind === "create" ||
      (local?.kind !== "delete" && confirmed.cells.has(id))
    );
  }

  function requireCell(id: Protocol.CellId) {
    assertActive();
    if (!hasCell(id)) {
      throw new Error(`Cell ${id} does not exist`);
    }
  }

  function updateCell(id: Protocol.CellId, patch: CellEdit) {
    requireCell(id);
    next = editCell(confirmed, next, id, patch);
  }

  const editor: DocumentEditor = {
    setCode: (id, code) => updateCell(id, { code }),
    setName: (id, name) => updateCell(id, { name }),
    updateConfig: (id, patch) =>
      updateCell(id, { config: Protocol.CellConfig.partial().parse(patch) }),
    createCell: (cell, placement = {}) => {
      assertActive();
      if (confirmed.cells.has(cell.id) || hasCell(cell.id)) {
        throw new Error(`Cell ${cell.id} already exists`);
      }
      if (placement.after !== undefined && placement.before !== undefined) {
        throw new Error("Specify either before or after for cell placement");
      }
      const anchor = placement.after ?? placement.before;
      if (anchor !== undefined) {
        requireCell(anchor);
      }
      next = createCell(next, cell, { ...placement });
    },
    deleteCell: (id) => {
      requireCell(id);
      next = deleteCell(next, id);
    },
    setOrder: (order) => {
      assertActive();
      const { cells } = viewDocument(confirmed, next);
      if (
        order.length !== cells.size ||
        new Set(order).size !== cells.size ||
        order.some((id) => !cells.has(id))
      ) {
        throw new Error("Cell order must contain every cell exactly once");
      }
      next = setOrder(next, order);
    },
  };

  try {
    const result: unknown = edit(editor);
    if (result instanceof Promise) {
      // Observe a rejected async callback without publishing its partial draft.
      result.catch(() => undefined);
      throw new Error("Document edit callbacks must be synchronous");
    }
    return next;
  } finally {
    active = false;
  }
}
