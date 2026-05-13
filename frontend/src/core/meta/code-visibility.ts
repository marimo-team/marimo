/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { KnownQueryParams } from "@/core/constants";
import { showCodeInRunModeAtom } from "@/core/meta/state";
import { kioskModeAtom, viewStateAtom } from "@/core/mode";
import { logNever } from "@/utils/assertNever";

/**
 * Whether the notebook source code reached the frontend and can be rendered.
 *
 * In `marimo run` the server omits cell sources unless `--include-code` is
 * set (every `cell.code` arrives as `""`). Use this to gate any "show code"
 * / "copy code" / "download .py" affordance.
 */
export function useNotebookCodeAvailable(
  cells: ReadonlyArray<{ code: string }>,
): boolean {
  const kioskMode = useAtomValue(kioskModeAtom);
  const { mode } = useAtomValue(viewStateAtom);
  const showInRunMode = useAtomValue(showCodeInRunModeAtom);

  if (kioskMode) {
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
      return cells.some((cell) => Boolean(cell.code));
    }
    default:
      logNever(mode);
      return false;
  }
}
