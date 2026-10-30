/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import {
  type Atom,
  atom,
  type createStore,
  type WritableAtom,
} from "jotai/vanilla";
import type { Document, NotebookBackend } from "../replica";
import type { EditableDocument } from "./draft";
import {
  createDocumentState,
  type DocumentEdit,
  type DocumentState,
} from "./state";
import { createDocumentSync, type DocumentSyncStatus } from "./sync";

export type { DocumentEdit, DocumentEditor } from "./state";
export type { EditableCell, EditableDocument } from "./draft";
export type { DocumentSyncStatus } from "./sync";

/** The editable document and its synchronization with the host. */
export interface DocumentModel {
  /** Confirmed host state with local drafts applied, null while unavailable or stopped. */
  readonly documentAtom: Atom<EditableDocument | null>;
  /** Ignored while stopped. */
  readonly editAtom: WritableAtom<null, [edit: DocumentEdit], void>;
  readonly syncStatusAtom: Atom<DocumentSyncStatus>;
  /** Drain local edits and return the confirmed revision. */
  flush(): Promise<Protocol.Document>;
  /** Retry a rejection against fresh state, or repeat an uncertain request exactly. */
  retry(): Promise<Protocol.Document>;
  /**
   * Edit and synchronize until the signal aborts, which discards local drafts.
   * The model can start again once stopped.
   */
  start(options: { signal: AbortSignal }): void;
}

interface Running {
  readonly state: DocumentState;
  readonly sync: ReturnType<typeof createDocumentSync>;
}

/** Create without subscribing to anything; editing begins on start. */
export function createDocumentModel({
  store,
  documentAtom: source,
  backendAtom,
}: {
  store: ReturnType<typeof createStore>;
  /** The document the host last confirmed. */
  documentAtom: Atom<Document | null>;
  /** The backend that confirmed it, whose commands reach its host. */
  backendAtom: Atom<NotebookBackend | null>;
}): DocumentModel {
  const runningAtom = atom<Running | null>(null);

  function stopped(): Promise<never> {
    return Promise.reject(new Error("The document model is not started"));
  }

  return {
    documentAtom: atom((get) => {
      const running = get(runningAtom);
      return running ? get(running.state.documentAtom) : null;
    }),
    editAtom: atom(null, (get, set, edit: DocumentEdit) => {
      const running = get(runningAtom);
      if (running) {
        set(running.state.editAtom, edit);
      }
    }),
    syncStatusAtom: atom((get) => {
      const running = get(runningAtom);
      return running ? get(running.sync.statusAtom) : { status: "unavailable" };
    }),
    flush: () => store.get(runningAtom)?.sync.flush() ?? stopped(),
    retry: () => store.get(runningAtom)?.sync.retry() ?? stopped(),
    start({ signal }) {
      signal.throwIfAborted();
      if (store.get(runningAtom)) {
        throw new Error("The document model is already started");
      }
      const state = createDocumentState({ store, source, signal });
      const sync = createDocumentSync({
        store,
        documentAtom: source,
        backendAtom,
        state,
        signal,
      });
      const stop = () => store.set(runningAtom, null);
      signal.addEventListener("abort", stop, { once: true });
      store.set(runningAtom, { state, sync });
      if (signal.aborted) {
        stop();
      }
    },
  };
}
