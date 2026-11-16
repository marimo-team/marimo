/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { maybeAddAltairImport } from "@/core/cells/add-missing-import";
import { useCellActions } from "@/core/cells/actions";
import { useLastFocusedCellId } from "@/core/cells/focus";
import { autoInstantiateAtom } from "@/core/config/config";

export function useAddCodeToNewCell(): (code: string) => void {
  const autoInstantiate = useAtomValue(autoInstantiateAtom);
  const lastFocusedCellId = useLastFocusedCellId();
  const { createCell } = useCellActions();

  return (code: string) => {
    if (code.includes("alt")) {
      maybeAddAltairImport({
        autoInstantiate,
        createCell,
        fromCellId: lastFocusedCellId,
      });
    }

    createCell({ after: lastFocusedCellId, code });
  };
}
