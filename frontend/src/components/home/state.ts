/* Copyright 2024 Marimo. All rights reserved. */

import { atomWithStorage } from "jotai/utils";
import React from "react";
import type { MarimoFile } from "@/core/network/types";
import { Functions } from "@/utils/functions";

export type RunningNotebooksMap = Map<string, MarimoFile>;

export const RunningNotebooksContext = React.createContext<{
  runningNotebooks: RunningNotebooksMap;
  setRunningNotebooks: (data: RunningNotebooksMap) => void;
}>({
  runningNotebooks: new Map(),
  setRunningNotebooks: Functions.NOOP,
});
export const WorkspaceRootContext = React.createContext<string>("");

export const includeMarkdownAtom = atomWithStorage<boolean>(
  "marimo:home:include-markdown",
  false,
  undefined,
  { getOnInit: true },
);
export const expandedFoldersAtom = atomWithStorage<Record<string, boolean>>(
  "marimo:home:expanded-folders",
  {},
  undefined,
  { getOnInit: true },
);
