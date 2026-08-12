/* Copyright 2026 Marimo. All rights reserved. */
import { atom } from "jotai";

/** Tagged so the progress label and error message can't drift apart. */
export type WasmInitState =
  | { kind: "loading"; message: string }
  | { kind: "ready" }
  | { kind: "error"; message: string };

export const wasmInitStateAtom = atom<WasmInitState>({
  kind: "loading",
  message: "Initializing...",
});
