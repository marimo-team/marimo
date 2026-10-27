/* Copyright 2026 Marimo. All rights reserved. */

import {
  atom,
  type Atom,
  type createStore,
  type WritableAtom,
} from "jotai/vanilla";
import type { Document } from "../host";
import * as Protocol from "@marimo-team/client/protocol";
import {
  acknowledge,
  type CellEdit,
  createCell,
  deleteCell,
  type Draft,
  type EditableDocument,
  editCell,
  EMPTY_DRAFT,
  isEmptyDraft,
  type Placement,
  prune,
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

/** A captured edit request. Return this same object when reporting its result. */
export interface DocumentSubmission {
  readonly notebookId: Protocol.NotebookId;
  readonly changes: readonly Protocol.Change[];
}

type ResponseRevision = Pick<Protocol.Document, "notebook_id" | "version">;

interface PendingSubmission {
  readonly submission: DocumentSubmission;
  readonly draft: Draft;
  readonly responseRevision: ResponseRevision | null;
}

interface ModelState {
  readonly confirmed: Document | null;
  readonly drafts: ReadonlyMap<Protocol.NotebookId, Draft>;
  readonly pending: PendingSubmission | null;
}

/**
 * Local edits over confirmed host state, with one submission in flight.
 *
 * A reset retains the submission so its receipt can reconcile a new snapshot.
 * Switching notebook identity invalidates it, retaining each notebook's draft.
 */
export interface DocumentState {
  /** Confirmed host state with local drafts applied, null while unavailable. */
  readonly documentAtom: Atom<EditableDocument | null>;
  /** Null when the document or source needed by a put is unavailable. */
  readonly changesAtom: Atom<readonly Protocol.Change[] | null>;
  /** Remains pending until both the response and its streamed revision arrive. */
  readonly pendingAtom: Atom<DocumentSubmission | null>;
  readonly editAtom: WritableAtom<null, [edit: DocumentEdit], void>;
  /** Capture a request, or null when unavailable, unchanged, or already sending. */
  readonly submitAtom: WritableAtom<null, [], DocumentSubmission | null>;
  /**
   * Report the response revision, or null for a rejected request.
   *
   * Success waits for a complete streamed document at that version or later.
   * Duplicate replies and replies for another notebook are ignored. Retry an
   * uncertain request with the same body and idempotency key; do not reject it
   * or capture a new request until its outcome is known.
   */
  readonly settleAtom: WritableAtom<
    null,
    [submission: DocumentSubmission, responseRevision: ResponseRevision | null],
    void
  >;
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

/** Publish the confirmed document and any released fields together. */
function reconcile(state: ModelState): ModelState {
  const { confirmed, pending } = state;
  if (confirmed === null) {
    return state;
  }
  let draft = draftOf(state);
  if (
    pending !== null &&
    pending.responseRevision !== null &&
    confirmed.revision.version >= pending.responseRevision.version
  ) {
    draft = acknowledge(draft, pending.draft);
    state = { ...state, pending: null };
  }
  return withDraft(state, prune(confirmed, draft, state.pending?.draft));
}

/** Internal draft and submission state for one editing lifetime. */
export function createDocumentState({
  store,
  source,
  signal,
}: {
  store: ReturnType<typeof createStore>;
  source: Atom<Document | null>;
  signal: AbortSignal;
}): DocumentState {
  signal.throwIfAborted();
  const stateAtom = atom<ModelState>({
    confirmed: store.get(source),
    drafts: new Map(),
    pending: null,
  });
  const documentAtom = atom((get): EditableDocument | null => {
    const state = get(stateAtom);
    return state.confirmed === null
      ? null
      : viewDocument(state.confirmed, draftOf(state));
  });
  const changesAtom = atom((get): readonly Protocol.Change[] | null => {
    const state = get(stateAtom);
    return state.confirmed === null
      ? null
      : toChanges(state.confirmed, draftOf(state));
  });
  const pendingAtom = atom((get) => get(stateAtom).pending?.submission ?? null);

  const unsubscribe = store.sub(source, () => {
    const confirmed = store.get(source);
    store.set(stateAtom, (state) =>
      reconcile({
        ...state,
        confirmed,
        pending:
          confirmed !== null &&
          state.pending !== null &&
          confirmed.revision.notebook_id !== state.pending.submission.notebookId
            ? null
            : state.pending,
      }),
    );
  });

  let editing = false;
  const editAtom = atom(null, (get, set, edit: DocumentEdit) => {
    if (editing) {
      throw new Error("Document transactions cannot be nested");
    }
    const state = get(stateAtom);
    if (signal.aborted || state.confirmed === null) {
      return;
    }
    editing = true;
    try {
      const draft = editDocument(
        state.confirmed,
        draftOf(state),
        edit,
        state.pending?.draft,
      );
      if (
        signal.aborted ||
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

  const submitAtom = atom(null, (get, set): DocumentSubmission | null => {
    const state = get(stateAtom);
    if (signal.aborted || state.confirmed === null || state.pending !== null) {
      return null;
    }
    const draft = draftOf(state);
    const changes = toChanges(state.confirmed, draft);
    if (changes === null) {
      return null;
    }
    if (changes.length === 0) {
      set(stateAtom, withDraft(state, EMPTY_DRAFT));
      return null;
    }
    const submission = {
      notebookId: state.confirmed.revision.notebook_id,
      changes,
    };
    set(stateAtom, {
      ...state,
      pending: { submission, draft, responseRevision: null },
    });
    return submission;
  });

  const settleAtom = atom(
    null,
    (
      get,
      set,
      submission: DocumentSubmission,
      responseRevision: ResponseRevision | null,
    ) => {
      const state = get(stateAtom);
      if (
        signal.aborted ||
        state.pending?.submission !== submission ||
        state.pending.responseRevision !== null
      ) {
        return;
      }
      if (
        responseRevision !== null &&
        responseRevision.notebook_id !== submission.notebookId
      ) {
        throw new Error("Edit response belongs to another notebook");
      }
      set(
        stateAtom,
        reconcile({
          ...state,
          pending:
            responseRevision === null
              ? null
              : { ...state.pending, responseRevision },
        }),
      );
    },
  );

  function stop() {
    unsubscribe();
    signal.removeEventListener("abort", stop);
    store.set(stateAtom, {
      confirmed: null,
      drafts: new Map(),
      pending: null,
    });
  }
  signal.addEventListener("abort", stop, { once: true });
  if (signal.aborted) {
    stop();
  }

  return {
    documentAtom,
    changesAtom,
    pendingAtom,
    editAtom,
    submitAtom,
    settleAtom,
  };
}

function editDocument(
  confirmed: Document,
  draft: Draft,
  edit: DocumentEdit,
  sent: Draft = EMPTY_DRAFT,
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
      next = deleteCell(next, id, sent);
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
