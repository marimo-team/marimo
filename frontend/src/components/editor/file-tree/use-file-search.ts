/* Copyright 2026 Marimo. All rights reserved. */

import { useCallback, useEffect, useRef, useState } from "react";
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
  const pending = useRef<Promise<void>>(Promise.resolve());
  const [revision, setRevision] = useState(0);
  const refetch = useCallback(() => setRevision((value) => value + 1), []);
  const [result, setResult] = useState<FileSearchState>({ status: "idle" });

  useEffect(() => {
    let cancelled = false;
    if (!query || query !== debouncedQuery) {
      return;
    }
    setResult({ status: "loading", query });
    // Let the in-flight server scan finish before starting another. Superseded
    // queued queries and remaining roots are skipped, keeping scan work bounded.
    const request = pending.current.then(async () => {
      const files: FileTreeNode[] = [];
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
          files.push(
            ...response.files.map((file): FileTreeNode => ({
              ...file,
              id: fileTreeNodeId(root.path, file.path),
              children: [],
              isRoot: false,
              rootPath: root.path,
              isPrimaryRoot: root.isPrimary,
            })),
          );
        } catch {
          failedRootCount += 1;
        }
      }
      if (!cancelled) {
        if (roots.length > 0 && failedRootCount === roots.length) {
          setResult({
            status: "error",
            query,
            error: new Error("Could not search any root"),
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
        const sortedFiles = files.toSorted(
          (left, right) =>
            rank(left) - rank(right) || left.name.localeCompare(right.name),
        );
        setResult({
          status: "success",
          isPartial: failedRootCount > 0,
          query,
          files: sortedFiles.slice(0, RESULT_LIMIT),
          hasMore: rootLimitReached || sortedFiles.length > RESULT_LIMIT,
        });
      }
    });
    pending.current = request.catch((error: unknown) => {
      if (!cancelled) {
        setResult({ status: "error", query, error });
      }
    });
    return () => {
      cancelled = true;
    };
  }, [query, debouncedQuery, tree, showHiddenFiles, revision, sendSearchFiles]);

  if (!query) {
    return { state: { status: "idle" }, refetch };
  }
  if (
    query !== debouncedQuery ||
    result.status === "idle" ||
    result.query !== query
  ) {
    return { state: { status: "loading", query }, refetch };
  }
  return { state: result, refetch };
}
