/* Copyright 2023 Marimo. All rights reserved. */

import { useState } from "react";
import { CellId } from "./ids";

// This does not need to be overcomplicated. We can just store the expanded
// state in a global map instead of Jotai since state is not shared between cells.
const expandedOutputs: Record<CellId, boolean> = {};

export function useExpandedOutput(cellId: CellId) {
  const [state, setState] = useState(expandedOutputs[cellId] ?? false);
  return [
    state,
    (expanded: boolean) => {
      setState(expanded);
      expandedOutputs[cellId] = expanded;
    },
  ] as const;
}
