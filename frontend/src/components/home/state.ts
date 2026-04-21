/* Copyright 2026 Marimo. All rights reserved. */

import { atomWithStorage } from "jotai/utils";
import React from "react";
import type { MarimoFile } from "@/core/network/types";
import { Functions } from "@/utils/functions";
import { jotaiJsonStorage } from "@/utils/storage/jotai";

export type RunningNotebooksMap = Map<string, MarimoFile>;

export const RunningNotebooksContext = React.createContext<{
  runningNotebooks: RunningNotebooksMap;
  setRunningNotebooks: (data: RunningNotebooksMap) => void;
}>({
  runningNotebooks: new Map(),
  setRunningNotebooks: Functions.NOOP,
});

/**
 * Context providing the workspace root plus a `refreshWorkspace` hook used by
 * file actions (rename/duplicate/delete) so they can invalidate both the
 * workspace tree and any sibling views (e.g. recent notebooks) in one call.
 */
export const WorkspaceContext = React.createContext<{
  root: string;
  refreshWorkspace: () => void;
}>({
  root: "",
  refreshWorkspace: Functions.NOOP,
});

export const includeMarkdownAtom = atomWithStorage<boolean>(
  "marimo:home:include-markdown",
  false,
  jotaiJsonStorage,
  { getOnInit: true },
);
export const expandedFoldersAtom = atomWithStorage<Record<string, boolean>>(
  "marimo:home:expanded-folders",
  {},
  jotaiJsonStorage,
  { getOnInit: true },
);
