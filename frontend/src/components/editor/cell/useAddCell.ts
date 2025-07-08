/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { maybeAddAltairImport } from "@/core/cells/add-missing-import";
import { useCellActions } from "@/core/cells/cells";
import { useLastFocusedCellId } from "@/core/cells/focus";
import { autoInstantiateAtom } from "@/core/config/config";

export function useAddCodeToNewCell(): (code: string) => void {
  const autoInstantiate = useAtomValue(autoInstantiateAtom);
  const lastFocusedCellId = useLastFocusedCellId();
  const { createNewCell } = useCellActions();

  return (code: string) => {
    if (code.includes("alt")) {
      maybeAddAltairImport(autoInstantiate, createNewCell, lastFocusedCellId);
    }

    createNewCell({
      code: code,
      before: false,
      cellId: lastFocusedCellId ?? "__end__",
    });
  };
}
