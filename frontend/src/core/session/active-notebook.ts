/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import type { DocumentModel } from "../notebook/document";
import type { NotebookReplica } from "../notebook/replica";

/** The replica owned by the mounted notebook session. */
export const activeNotebookReplicaAtom = atom<NotebookReplica | null>(null);

/** The document model owned by the mounted notebook session. */
export const activeDocumentModelAtom = atom<DocumentModel | null>(null);

/** The document the host last confirmed, or null while no notebook is connected. */
export const confirmedDocumentAtom = atom((get) => {
  const replica = get(activeNotebookReplicaAtom);
  return replica === null ? null : get(replica.documentAtom);
});
