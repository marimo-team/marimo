/* Copyright 2026 Marimo. All rights reserved. */

import { atom, useAtomValue } from "jotai";
import { useAsyncData } from "@/hooks/useAsyncData";
import { createReducerAndAtoms } from "@/utils/createReducer";
import type { NotificationMessageData } from "../kernel/messages";
import type { VariableName } from "../variables/types";
import { ListStorageEntries } from "./request-registry";
import type { StorageEntry, StorageState } from "./types";
import {
  DEFAULT_FETCH_LIMIT,
  ROOT_PATH,
  storageNamespacePrefix,
  storagePathKey,
} from "./types";

function initialState(): StorageState {
  return {
    namespaces: [],
    entriesByPath: new Map(),
  };
}

const {
  reducer,
  createActions,
  valueAtom: storageAtom,
  useActions,
} = createReducerAndAtoms(initialState, {
  setNamespaces: (
    state,
    data: NotificationMessageData<"storage-namespaces">,
  ) => {
    // Merge/replace namespaces by name
    const existingMap = new Map(state.namespaces.map((ns) => [ns.name, ns]));
    for (const ns of data.namespaces) {
      existingMap.set(ns.name, ns);
    }
    return {
      ...state,
      namespaces: [...existingMap.values()],
    };
  },

  setEntries: (
    state,
    opts: {
      namespace: string;
      prefix: string | null | undefined;
      entries: StorageEntry[];
    },
  ) => {
    const key = storagePathKey(opts.namespace, opts.prefix);
    const entriesByPath = new Map(state.entriesByPath);
    entriesByPath.set(key, opts.entries);
    return { ...state, entriesByPath };
  },

  clearNamespaceCache: (state, namespace: string) => {
    const entriesByPath = new Map(state.entriesByPath);
    const prefix = storageNamespacePrefix(namespace);
    for (const key of entriesByPath.keys()) {
      if (key.startsWith(prefix)) {
        entriesByPath.delete(key);
      }
    }
    return { ...state, entriesByPath };
  },

  filterFromVariables: (state, variableNames: VariableName[]) => {
    const names = new Set(variableNames);
    // Filter out namespaces whose backing variable is no longer in scope
    const namespaces = state.namespaces.filter((ns) => {
      return names.has(ns.name as VariableName);
    });
    return { ...state, namespaces };
  },
});

/**
 * React hook to get the storage state.
 */
export const useStorage = () => useAtomValue(storageAtom);

export const storageNamespacesAtom = atom((get) => get(storageAtom).namespaces);

/**
 * React hook to get the storage actions.
 */
export function useStorageActions() {
  return useActions();
}

export { storageAtom };

/**
 * Hook that fetches and caches storage entries for a given namespace/prefix.
 * Entries are fetched on first access and cached in the store for subsequent renders.
 */
export function useStorageEntries(namespace: string, prefix?: string) {
  const { entriesByPath } = useStorage();
  const { setEntries } = useStorageActions();
  const cached = entriesByPath.get(storagePathKey(namespace, prefix));

  const { isPending, error, refetch } = useAsyncData(async () => {
    if (cached) {
      return;
    }
    const result = await ListStorageEntries.request({
      namespace,
      prefix: prefix ?? ROOT_PATH,
      limit: DEFAULT_FETCH_LIMIT,
    });
    if (result.error) {
      throw new Error(result.error);
    }
    setEntries({ namespace, prefix, entries: result.entries });
  }, [namespace, prefix, cached === undefined]);

  return {
    entries: cached ?? [],
    isPending: isPending && !cached,
    error: cached ? undefined : error,
    refetch,
  };
}

export const exportedForTesting = {
  reducer,
  createActions,
  initialState,
};
