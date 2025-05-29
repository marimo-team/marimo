/* Copyright 2024 Marimo. All rights reserved. */
import { atom } from "jotai";

const BUILD_VERSION: string = import.meta.env.VITE_MARIMO_VERSION || "unknown";

export const marimoVersionAtom = atom<string>(BUILD_VERSION);

export const showCodeInRunModeAtom = atom<boolean>(true);

export const serverTokenAtom = atom<string | null>(null);
