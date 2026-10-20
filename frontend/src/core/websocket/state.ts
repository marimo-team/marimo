/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import type { NotebookClient } from "../host/notebook-client";

/** The client owned by the mounted notebook session. */
export const notebookClientAtom = atom<NotebookClient | null>(null);
