/* Copyright 2026 Marimo. All rights reserved. */
import { atom } from "jotai";

export interface TracebackData {
  traceback: string;
  errorMessage: string;
}

export const tracebackModalAtom = atom<TracebackData | null>(null);
