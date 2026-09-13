/* Copyright 2026 Marimo. All rights reserved. */
import { atom } from "jotai";
import type { SandboxResponse } from "@/core/network/types";

export const sandboxAtom = atom<SandboxResponse | null>(null);
export const sandboxSyncAtom = atom<{ pending: boolean; error: string | null }>(
  {
    pending: false,
    error: null,
  },
);
export const sandboxActionsAtom = atom<{
  sync: () => Promise<boolean>;
  editManifest: () => Promise<void>;
} | null>(null);
