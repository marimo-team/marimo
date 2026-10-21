/* Copyright 2026 Marimo. All rights reserved. */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRequestClient } from "@/core/network/requests";
import { useDebounce } from "@/hooks/useDebounce";
import {
  fileTreeNodeId,
  type FileTreeNode,
  type RequestingTree,
} from "./requesting-tree";

const RESULT_LIMIT = 200;

export type FileSearchState =
  | { status: "idle" }
  | { status: "loading"; query: string }
  | { status: "error"; query: string; error: unknown }
  | {
      status: "success";
      query: string;
      files: FileTreeNode[];
      hasMore: boolean;
      isPartial: boolean;
    };

export function useFileSearch({
  query,
  tree,
  showHiddenFiles,
}: {
  query: string;
  tree: RequestingTree;
  showHiddenFiles: boolean;
}): { state: FileSearchState; refetch: () => void } {
  const { sendSearchFiles } = useRequestClient();
  const debouncedQuery = useDebounce(query, 300);
  // Nullable so the ref is not built on every render
  const pending = useRef<Promise<void> | null>(null);
  const [revision, setRevision] = useState(0);
  const refetch = useCallback(() => setRevision((value) => value + 1), []);
  const requestIdentity = useMemo(
    () => ({ query, tree, showHiddenFiles, revision, sendSearchFiles }),
    [query, tree, showHiddenFiles, revision, sendSearchFiles],
  );
  const [result, setResult] = useState<{
    requestIdentity: typeof requestIdentity;
    state: FileSearchState;
  }>();

  useEffect(() => {
    // Read inputs through requestIdentity so it alone drives new requests
    const { query, tree, showHiddenFiles, sendSearchFiles } = requestIdentity;
    let cancelled = false;
    if (!query || query !== debouncedQuery) {
      return;
    }
    // Let the in-flight server scan finish before starting another. Superseded
    // queued queries and remaining roots are skipped, keeping scan work bounded.
    const request = (pending.current ?? Promise.resolve()).then(async () => {
      const filesByPath = new Map<string, FileTreeNode>();
      let rootLimitReached = false;
      let failedRootCount = 0;
      const roots = tree.getRoots();
      for (const root of roots) {
        if (cancelled) {
          return;
        }
        try {
          const response = await sendSearchFiles({
            query,
            path: root.path,
            includeFiles: true,
            includeDirectories: true,
            includeHidden: showHiddenFiles,
            depth: 20,
            limit: RESULT_LIMIT,
          });
          rootLimitReached ||= response.files.length >= RESULT_LIMIT;
          for (const file of response.files) {
            const existing = filesByPath.get(file.path);
            if (existing && (!root.isPrimary || existing.isPrimaryRoot)) {
              continue;
            }
            filesByPath.set(file.path, {
              ...file,
              id: fileTreeNodeId(root.path, file.path),
              children: [],
              isRoot: false,
              rootPath: root.path,
              isPrimaryRoot: root.isPrimary,
            });
          }
        } catch {
          failedRootCount += 1;
        }
      }
      if (!cancelled) {
        if (roots.length > 0 && failedRootCount === roots.length) {
          setResult({
            requestIdentity,
            state: {
              status: "error",
              query,
              error: new Error("Could not search any root"),
            },
          });
          return;
        }
        const rank = (file: FileTreeNode) => {
          const name = file.name.toLowerCase();
          const needle = query.toLowerCase();
          if (name === needle) {
            return 0;
          }
          if (name.startsWith(needle)) {
            return 1;
          }
          return 2;
        };
        const sortedFiles = [...filesByPath.values()].toSorted(
          (left, right) =>
            rank(left) - rank(right) || left.name.localeCompare(right.name),
        );
        setResult({
          requestIdentity,
          state: {
            status: "success",
            isPartial: failedRootCount > 0,
            query,
            files: sortedFiles.slice(0, RESULT_LIMIT),
            hasMore: rootLimitReached || sortedFiles.length > RESULT_LIMIT,
          },
        });
      }
    });
    pending.current = request.catch((error: unknown) => {
      if (!cancelled) {
        setResult({
          requestIdentity,
          state: { status: "error", query, error },
        });
      }
    });
    return () => {
      cancelled = true;
    };
  }, [debouncedQuery, requestIdentity]);

  if (!query) {
    return { state: { status: "idle" }, refetch };
  }
  if (query !== debouncedQuery || result?.requestIdentity !== requestIdentity) {
    return { state: { status: "loading", query }, refetch };
  }
  return { state: result.state, refetch };
}
