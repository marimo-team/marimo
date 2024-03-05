/* Copyright 2024 Marimo. All rights reserved. */
import { atom } from "jotai";
import { CellId } from "../cells/ids";

export const aiCompletionCellAtom = atom<CellId | null>(null);
export const includeOtherCellsAtom = atom<boolean>(false);
