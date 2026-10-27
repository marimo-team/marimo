/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import type { Atom, createStore } from "jotai/vanilla";
import type { NotebookBackend } from "../host/backend";
import type { Document } from "../host/resources/document";
import { createDocumentState, type DocumentState } from "./state";
import { createDocumentSync, type DocumentSyncStatus } from "./sync";

export type { DocumentEdit, DocumentEditor } from "./state";
export type { EditableCell, EditableDocument } from "./draft";
export type { DocumentSyncStatus } from "./sync";

/** The editable document and its synchronization with the host. */
export interface DocumentModel extends Pick<
  DocumentState,
  "documentAtom" | "editAtom"
> {
  readonly syncStatusAtom: Atom<DocumentSyncStatus>;
  /** Drain local edits and return the confirmed revision. */
  flush(): Promise<Protocol.Document>;
  /** Retry a rejection against fresh state, or repeat an uncertain request exactly. */
  retry(): Promise<Protocol.Document>;
}

/** Create once per editing session; abort to stop editing and synchronization together. */
export function createDocumentModel({
  store,
  documentAtom,
  backendAtom,
  signal,
}: {
  store: ReturnType<typeof createStore>;
  /** The document the host last confirmed. */
  documentAtom: Atom<Document | null>;
  /** The backend that confirmed it, whose commands reach its host. */
  backendAtom: Atom<NotebookBackend | null>;
  signal: AbortSignal;
}): DocumentModel {
  signal.throwIfAborted();
  const state = createDocumentState({ store, source: documentAtom, signal });
  const sync = createDocumentSync({
    store,
    documentAtom,
    backendAtom,
    state,
    signal,
  });
  return {
    documentAtom: state.documentAtom,
    editAtom: state.editAtom,
    syncStatusAtom: sync.statusAtom,
    flush: sync.flush,
    retry: sync.retry,
  };
}
