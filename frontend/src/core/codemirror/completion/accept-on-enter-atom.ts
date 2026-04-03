/* Copyright 2026 Marimo. All rights reserved. */
import { atomWithStorage } from "jotai/utils";
import { jotaiJsonStorage } from "@/utils/storage/jotai";
// Default: true (Enter accepts suggestion, matching VS Code default)
export const acceptCompletionOnEnterAtom = atomWithStorage<boolean>(
  "marimo:accept-completion-on-enter",
  true,
  jotaiJsonStorage,
  { getOnInit: true },
);
