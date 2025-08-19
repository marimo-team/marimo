/* Copyright 2024 Marimo. All rights reserved. */
import { atom, useAtomValue } from "jotai";
import { isStaticNotebook } from "@/core/static/static-state";
import { store } from "../state/jotai";
import { RuntimeManager } from "./runtime";
import type { RuntimeConfig } from "./types";

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
const runtimeManagerAtom = atom<RuntimeManager>((get) => {
  const config = get(runtimeConfigAtom);
  // "lazy" means that the runtime manager will attempt to connect to a
  // server, which in the case of a static notebook, will not be available.
  const lazy = isStaticNotebook();
  return new RuntimeManager(config, lazy);
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
  let base = getRuntimeManager().httpURL.toString();
  if (base.startsWith("blob:")) {
    // Remove leading blob:
    base = base.replace("blob:", "");
  }
  return new URL(path, base);
}
