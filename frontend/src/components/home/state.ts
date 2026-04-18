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
export const WorkspaceContext = React.createContext<{
  root: string;
  refreshAll: () => void;
}>({
  root: "",
  refreshAll: Functions.NOOP,
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
