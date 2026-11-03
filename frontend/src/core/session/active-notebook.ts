/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import type { DocumentModel } from "../notebook/document";
import type { NotebookReplica } from "../notebook/replica";

/** The replica owned by the mounted notebook session. */
export const activeNotebookReplicaAtom = atom<NotebookReplica | null>(null);

/** The document model owned by the mounted notebook session. */
export const activeDocumentModelAtom = atom<DocumentModel | null>(null);
