/* Copyright 2026 Marimo. All rights reserved. */

import type { CellAnalysis } from "@marimo-team/client/protocol";
import { atom, useAtomValue } from "jotai";
import { useMemo } from "react";
import { notebookAnalysisAtom } from "../session/active-notebook";
import type { CellId } from "./ids";

export function reusableDefinition(cell: CellAnalysis | undefined) {
  return cell?.diagnostics.find(
    ({ source, kind }) =>
      source === "marimo" &&
      (kind === "reusable-definition" || kind === "non-reusable-definition"),
  );
}

export function useReusableDefinition(id: CellId) {
  return useAtomValue(
    useMemo(
      () =>
        atom((get) => reusableDefinition(get(notebookAnalysisAtom)?.cells[id])),
      [id],
    ),
  );
}
