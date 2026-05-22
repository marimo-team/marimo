/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

import { useInternalStateWithSync } from "@/hooks/useInternalStateWithSync";
import type { VisibilityState } from "@tanstack/react-table";
import { dequal as isDeepEqual } from "dequal";
import type React from "react";

interface UseColumnVisibilityResult {
  columnVisibility: VisibilityState;
  setColumnVisibility: React.Dispatch<React.SetStateAction<VisibilityState>>;
}

export function useColumnVisibility(
  hiddenColumns?: string[],
): UseColumnVisibilityResult {
  const [columnVisibility, setColumnVisibility] =
    useInternalStateWithSync<VisibilityState>(
      Object.fromEntries((hiddenColumns ?? []).map((c) => [c, false])),
      isDeepEqual,
    );

  return { columnVisibility, setColumnVisibility };
}
