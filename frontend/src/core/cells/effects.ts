/* Copyright 2024 Marimo. All rights reserved. */

import { debounce, isEqual } from "lodash-es";
import type { MultiColumn } from "@/utils/id-tree";
import { kioskModeAtom } from "../mode";
import { syncCellIds } from "../network/requests";
import type { UpdateCellIdsRequest } from "../network/types";
import { store } from "../state/jotai";
import type { CellId } from "./ids";

const debounceSyncCellIds = debounce(syncCellIds, 400);

export const CellEffects = {
  onCellIdsChange: (
    cellIds: MultiColumn<CellId>,
    prevCellIds: MultiColumn<CellId>,
  ) => {
    const kioskMode = store.get(kioskModeAtom);
    if (kioskMode) {
      return;
    }
    // If cellIds is empty, return early
    if (cellIds.isEmpty()) {
      return;
    }
    // If prevCellIds is empty, also return early
    // this means that the notebook was just created
    if (prevCellIds.isEmpty()) {
      return;
    }

    // If they are different references, send an update to the server
    if (!isEqual(cellIds.inOrderIds, prevCellIds.inOrderIds)) {
      // "name" property is not actually required
      void debounceSyncCellIds({
        cell_ids: cellIds.inOrderIds,
      } as unknown as UpdateCellIdsRequest);
    }
  },
};
