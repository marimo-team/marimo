/* Copyright 2024 Marimo. All rights reserved. */

import { useAtom } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { store } from "@/core/state/jotai";

const BASE_KEY = "marimo:notebook-sql-mode";

export type SQLMode = "validate" | "default";

const sqlModeAtom = atomWithStorage<SQLMode>(BASE_KEY, "default");

export function useSQLMode() {
  const [sqlMode, setSQLMode] = useAtom(sqlModeAtom);
  return { sqlMode, setSQLMode };
}

export function getSQLMode() {
  return store.get(sqlModeAtom);
}
