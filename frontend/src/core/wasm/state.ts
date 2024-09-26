/* Copyright 2024 Marimo. All rights reserved. */
import { atom } from "jotai";
import { notebookAtom } from "../cells/cells";

export const wasmInitializationAtom = atom<string>("Initializing...");

export const hasAnyOutputAtom = atom<boolean>((get) => {
  const notebook = get(notebookAtom);
  return Object.values(notebook.cellRuntime).some((runtime) =>
    Boolean(runtime.output),
  );
});
