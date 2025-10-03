/* Copyright 2024 Marimo. All rights reserved. */

import { useAtom } from "jotai";
import { atomWithStorage } from "jotai/utils";

const BASE_KEY = "marimo:ai-autofix-mode";

const fixModeAtom = atomWithStorage<"prompt" | "autofix">(BASE_KEY, "autofix");

export function useFixMode() {
  const [fixMode, setFixMode] = useAtom(fixModeAtom);
  return { fixMode, setFixMode };
}
