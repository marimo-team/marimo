/* Copyright 2024 Marimo. All rights reserved. */

import { useAtom } from "jotai";
import { atomWithStorage } from "jotai/utils";

export type FixMode = "prompt" | "autofix";

const BASE_KEY = "marimo:ai-autofix-mode";

const fixModeAtom = atomWithStorage<FixMode>(BASE_KEY, "autofix");

export function useFixMode() {
  const [fixMode, setFixMode] = useAtom(fixModeAtom);
  return { fixMode, setFixMode };
}
