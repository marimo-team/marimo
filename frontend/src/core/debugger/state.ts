/* Copyright 2023 Marimo. All rights reserved. */
import { atom } from "jotai";
import { OutputMessage } from "../kernel/messages";

interface DebuggerState {
  cellId: string;
  outputs: OutputMessage[];
}

export const debuggerAtom = atom<DebuggerState | undefined>(undefined);
