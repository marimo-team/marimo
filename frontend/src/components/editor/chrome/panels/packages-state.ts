/* Copyright 2024 Marimo. All rights reserved. */
import { atom } from "jotai";

// Atom to store the packages to prefill in the packages panel
export const packagesToInstallAtom = atom<string | null>(null);
