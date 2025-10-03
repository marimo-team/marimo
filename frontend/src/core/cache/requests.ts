/* Copyright 2024 Marimo. All rights reserved. */
import { atom } from "jotai";
import type { CacheInfoFetched } from "../kernel/messages";

export const cacheInfoAtom = atom<CacheInfoFetched | null>(null);
