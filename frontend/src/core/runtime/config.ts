/* Copyright 2024 Marimo. All rights reserved. */
import { atom, useAtomValue } from "jotai";
import type { RuntimeConfig } from "./types";
import { RuntimeManager } from "./runtime";
import { store } from "../state/jotai";

function getBaseURI(): string {
  const url = new URL(document.baseURI);
  url.search = "";
  url.hash = "";
  return url.toString();
}

export const DEFAULT_RUNTIME_CONFIG: RuntimeConfig = {
  url: getBaseURI(),
};

export const runtimeConfigAtom = atom<RuntimeConfig>(DEFAULT_RUNTIME_CONFIG);
export const runtimeManagerAtom = atom<RuntimeManager>((get) => {
  const config = get(runtimeConfigAtom);
  return new RuntimeManager(config);
});

export function useRuntimeManager(): RuntimeManager {
  return useAtomValue(runtimeManagerAtom);
}

/**
 * Prefer to use useRuntimeManager instead of this function.
 */
export function getRuntimeManager(): RuntimeManager {
  return store.get(runtimeManagerAtom);
}

export function asRemoteURL(path: string): URL {
  if (path.startsWith("http")) {
    return new URL(path);
  }
  return new URL(path, getRuntimeManager().httpURL.toString());
}
