/* Copyright 2024 Marimo. All rights reserved. */

import { atom } from "jotai";
import type { CellId } from "./ids";

export const pendingDeleteCellsAtom = atom<Set<CellId>>(new Set<CellId>());
