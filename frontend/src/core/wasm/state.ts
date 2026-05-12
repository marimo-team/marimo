/* Copyright 2026 Marimo. All rights reserved. */
import { atom } from "jotai";
import { notebookAtom } from "../cells/cells";
import { isOutputEmpty } from "../cells/outputs";

/** Tagged so the progress label and error message can't drift apart. */
export type WasmInitState =
  | { kind: "loading"; message: string }
  | { kind: "ready" }
  | { kind: "error"; message: string };

export const wasmInitStateAtom = atom<WasmInitState>({
  kind: "loading",
  message: "Initializing...",
});

export const hasAnyOutputAtom = atom<boolean>((get) => {
  const notebook = get(notebookAtom);
  const runtimeStates = Object.values(notebook.cellRuntime);
  // First check if there is any output
  const hasOutput = runtimeStates.some(
    (runtime) => !isOutputEmpty(runtime.output),
  );
  if (hasOutput) {
    return true;
  }
  // If there is no output, check if they have all run to completion
  // in case this notebook doesn't contain outputs
  return runtimeStates.every((runtime) => runtime.status === "idle");
});
