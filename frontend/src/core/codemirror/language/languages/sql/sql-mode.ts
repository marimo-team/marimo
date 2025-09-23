/* Copyright 2024 Marimo. All rights reserved. */

import { atom, useAtom } from "jotai";
import { store } from "@/core/state/jotai";

export type SQLMode = "validate" | "default";

// TODO: Maybe make this atom with storage, per notebook
const sqlModeAtom = atom<SQLMode>("default");

export function useSQLMode() {
  const [sqlMode, setSQLMode] = useAtom(sqlModeAtom);
  return { sqlMode, setSQLMode };
}

export function getSQLMode() {
  return store.get(sqlModeAtom);
}
