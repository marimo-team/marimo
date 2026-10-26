/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import type { Atom, createStore } from "jotai/vanilla";
import { createDocumentState, type DocumentState } from "./state";
import {
  createDocumentSync,
  type DocumentHost,
  type DocumentSyncState,
} from "./sync";

export type { DocumentEdit, DocumentEditor } from "./state";
export type { DocumentHost, DocumentSyncState } from "./sync";

/** The editable document and its synchronization with the host. */
export interface DocumentModel extends Pick<
  DocumentState,
  "cellAtom" | "orderAtom" | "appConfigAtom" | "editAtom"
> {
  readonly syncStateAtom: Atom<DocumentSyncState>;
  /** Drain local edits and return the confirmed revision. */
  flush(): Promise<Protocol.Document>;
  /** Retry a rejection against fresh state, or repeat an uncertain request exactly. */
  retry(): Promise<Protocol.Document>;
}

/** Create once per editing session; abort to stop editing and synchronization together. */
export function createDocumentModel({
  store,
  notebook,
  signal,
}: {
  store: ReturnType<typeof createStore>;
  notebook: DocumentHost;
  signal: AbortSignal;
}): DocumentModel {
  signal.throwIfAborted();
  const state = createDocumentState({
    store,
    source: notebook.documentAtom,
    signal,
  });
  const sync = createDocumentSync({ store, notebook, state, signal });
  return {
    cellAtom: state.cellAtom,
    orderAtom: state.orderAtom,
    appConfigAtom: state.appConfigAtom,
    editAtom: state.editAtom,
    syncStateAtom: sync.stateAtom,
    flush: sync.flush,
    retry: sync.retry,
  };
}
