/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import type { NotebookReplica } from "../host";

/** The replica owned by the mounted notebook session. */
export const notebookReplicaAtom = atom<NotebookReplica | null>(null);
