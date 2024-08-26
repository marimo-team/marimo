/* Copyright 2024 Marimo. All rights reserved. */
import React, {} from "react";
import { Functions } from "@/utils/functions";
import { atomWithStorage } from "jotai/utils";
import type { MarimoFile } from "@/core/network/types";

export type RunningNotebooksMap = Map<string, MarimoFile>;

export const RunningNotebooksContext = React.createContext<{
  runningNotebooks: RunningNotebooksMap;
  setRunningNotebooks: (data: RunningNotebooksMap) => void;
  root: string;
}>({
  runningNotebooks: new Map(),
  root: "",
  setRunningNotebooks: Functions.NOOP,
});

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
