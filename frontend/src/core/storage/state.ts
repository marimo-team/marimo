/* Copyright 2026 Marimo. All rights reserved. */

import { atom, useAtomValue } from "jotai";
import { useCallback, useRef, useState } from "react";
import { useAsyncData } from "@/hooks/useAsyncData";
import { createReducerAndAtoms } from "@/utils/createReducer";
import type { NotificationMessageData } from "../kernel/messages";
import type { VariableName } from "../variables/types";
import {
  ListStorageEntries,
  type StorageEntriesResult,
} from "./request-registry";
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
    pageMetadataByPath: new Map(),
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
      nextPageToken?: string | null;
      mayHaveMore?: boolean;
      append?: boolean;
    },
  ) => {
    const key = storagePathKey(opts.namespace, opts.prefix);
    const entriesByPath = new Map(state.entriesByPath);
    const entries =
      opts.append && entriesByPath.has(key)
        ? [...(entriesByPath.get(key) ?? []), ...opts.entries]
        : opts.entries;
    entriesByPath.set(key, entries);

    const pageMetadataByPath = new Map(state.pageMetadataByPath);
    pageMetadataByPath.set(key, {
      nextPageToken: opts.nextPageToken ?? null,
      mayHaveMore: opts.mayHaveMore ?? false,
    });
    return {
      ...state,
      entriesByPath,
      pageMetadataByPath,
    };
  },

  clearNamespaceCache: (state, namespace: string) => {
    const entriesByPath = new Map(state.entriesByPath);
    const pageMetadataByPath = new Map(state.pageMetadataByPath);
    const prefix = storageNamespacePrefix(namespace);
    for (const key of entriesByPath.keys()) {
      if (key.startsWith(prefix)) {
        entriesByPath.delete(key);
      }
    }
    for (const key of pageMetadataByPath.keys()) {
      if (key.startsWith(prefix)) {
        pageMetadataByPath.delete(key);
      }
    }
    return {
      ...state,
      entriesByPath,
      pageMetadataByPath,
    };
  },

  filterFromVariables: (state, variableNames: VariableName[]) => {
    const names = new Set(variableNames);
    // Filter out namespaces whose backing variable is no longer in scope
    const namespaces = state.namespaces.filter((ns) => {
      return names.has(ns.name);
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

async function fetchStorageEntriesPage({
  namespace,
  prefix,
  pageToken,
  append,
  setEntries,
}: {
  namespace: string;
  prefix: string | null | undefined;
  pageToken?: string | null;
  append?: boolean;
  setEntries: ReturnType<typeof useStorageActions>["setEntries"];
}): Promise<StorageEntriesResult> {
  const result = await ListStorageEntries.request({
    namespace,
    prefix: prefix ?? ROOT_PATH,
    limit: DEFAULT_FETCH_LIMIT,
    ...(pageToken ? { pageToken } : {}),
  });
  if (result.error) {
    throw new Error(result.error);
  }
  setEntries({
    namespace,
    prefix,
    entries: result.entries,
    nextPageToken: result.next_page_token,
    mayHaveMore: result.may_have_more,
    append,
  });
  return result;
}

/**
 * Hook that fetches and caches storage entries for a given namespace/prefix.
 * Entries are fetched on first access and cached in the store for subsequent renders.
 */
export function useStorageEntries(namespace: string, prefix?: string) {
  const { entriesByPath, pageMetadataByPath } = useStorage();
  const { setEntries } = useStorageActions();
  const key = storagePathKey(namespace, prefix);
  const cached = entriesByPath.get(key);
  const metadata = pageMetadataByPath.get(key);
  const nextPageToken = metadata?.nextPageToken ?? null;
  const mayHaveMore = metadata?.mayHaveMore ?? false;
  const isLoadingMoreRef = useRef(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [loadMoreError, setLoadMoreError] = useState<Error | undefined>();

  const { isPending, error, refetch } = useAsyncData(async () => {
    if (cached) {
      return;
    }
    await fetchStorageEntriesPage({
      namespace,
      prefix,
      setEntries,
    });
  }, [namespace, prefix, cached === undefined]);

  const loadMore = useCallback(async () => {
    if (!nextPageToken || isLoadingMoreRef.current) {
      return;
    }

    isLoadingMoreRef.current = true;
    setIsLoadingMore(true);
    setLoadMoreError(undefined);
    try {
      await fetchStorageEntriesPage({
        namespace,
        prefix,
        pageToken: nextPageToken,
        append: true,
        setEntries,
      });
    } catch (error) {
      setLoadMoreError(
        error instanceof Error ? error : new Error(String(error)),
      );
    } finally {
      isLoadingMoreRef.current = false;
      setIsLoadingMore(false);
    }
  }, [namespace, prefix, nextPageToken, setEntries]);

  return {
    entries: cached ?? [],
    isPending: isPending && !cached,
    error: cached ? undefined : error,
    hasMore: nextPageToken !== null,
    mayHaveMore: nextPageToken === null && mayHaveMore,
    loadMore,
    isLoadingMore,
    loadMoreError,
    refetch,
  };
}

export function useStoragePageFetcher() {
  const { setEntries } = useStorageActions();
  return useCallback(
    (opts: {
      namespace: string;
      prefix: string | null | undefined;
      pageToken?: string | null;
      append?: boolean;
    }) =>
      fetchStorageEntriesPage({
        ...opts,
        setEntries,
      }),
    [setEntries],
  );
}

export const exportedForTesting = {
  reducer,
  createActions,
  initialState,
};
