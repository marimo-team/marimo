/* Copyright 2026 Marimo. All rights reserved. */

import { useAtom } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { store } from "@/core/state/jotai";
import { jotaiJsonStorage } from "@/utils/storage/jotai";

const BASE_KEY = "marimo:notebook-sql-mode";

export type SQLMode = "validate" | "default";

const sqlModeAtom = atomWithStorage<SQLMode>(
  BASE_KEY,
  "default",
  jotaiJsonStorage,
);

export function useSQLMode() {
  const [sqlMode, setSQLMode] = useAtom(sqlModeAtom);
  return { sqlMode, setSQLMode };
}

export function getSQLMode() {
  return store.get(sqlModeAtom);
}
