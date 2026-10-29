/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import type { NotebookReplica } from "../notebook/replica";

/** The replica owned by the mounted notebook session. */
export const activeNotebookReplicaAtom = atom<NotebookReplica | null>(null);
