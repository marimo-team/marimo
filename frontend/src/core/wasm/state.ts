/* Copyright 2024 Marimo. All rights reserved. */
import { atom } from "jotai";
import { notebookAtom } from "../cells/cells";
import { isOutputEmpty } from "../cells/outputs";

export const wasmInitializationAtom = atom<string>("Initializing...");

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
