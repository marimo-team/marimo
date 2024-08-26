/* Copyright 2024 Marimo. All rights reserved. */
import { atom } from "jotai";
import type { CellId } from "../cells/ids";

export const aiCompletionCellAtom = atom<{
  cellId: CellId;
  initialPrompt?: string;
} | null>(null);
export const includeOtherCellsAtom = atom<boolean>(false);
