/* Copyright 2026 Marimo. All rights reserved. */

import { atom, useAtomValue } from "jotai";
import { KnownQueryParams } from "@/core/constants";
import { showCodeInRunModeAtom } from "@/core/meta/state";
import { kioskModeAtom, viewStateAtom } from "@/core/mode";
import { runtimeAdapterAtom } from "@/core/runtime/adapter";
import { confirmedDocumentAtom } from "@/core/session/active-notebook";
import { logNever } from "@/utils/assertNever";

/** Whether any cell's source reached this client. A host withholds source as null. */
export const codeAvailableAtom = atom((get) => {
  const document = get(confirmedDocumentAtom);
  return (
    document !== null &&
    [...document.cells.values()].some((cell) => cell.code !== null)
  );
});

/**
 * Whether the notebook source code can be rendered.
 *
 * In `marimo run` the server withholds cell sources unless `--include-code`
 * is set. Use this to gate any "show code" / "copy code" / "download .py"
 * affordance.
 */
export function useNotebookCodeAvailable(): boolean {
  const available = useAtomValue(codeAvailableAtom);
  const kioskMode = useAtomValue(kioskModeAtom);
  const { mode } = useAtomValue(viewStateAtom);
  const showInRunMode = useAtomValue(showCodeInRunModeAtom);
  const runtimeKind = useAtomValue(runtimeAdapterAtom).kind;

  if (kioskMode && runtimeKind === "remote") {
    return true;
  }

  switch (mode) {
    case "edit":
    case "present":
      return true;
    case "home":
    case "gallery":
      return false;
    case "read": {
      if (!showInRunMode) {
        return false;
      }
      const params = new URLSearchParams(window.location.search);
      if (params.get(KnownQueryParams.includeCode) === "false") {
        return false;
      }
      return available;
    }
    default:
      logNever(mode);
      return false;
  }
}
