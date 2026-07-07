/* Copyright 2026 Marimo. All rights reserved. */

import { outputIsLoading, outputIsStale } from "@/core/cells/cell";
import { OutputArea } from "../editor/Output";
import { memo } from "react";
import type { CellId } from "@/core/cells/ids";
import type { CellRuntimeState } from "@/core/cells/types";

interface SlideContentProps extends Pick<
  CellRuntimeState,
  "output" | "status" | "interrupted" | "staleInputs" | "runStartTimestamp"
> {
  cellId: CellId;
}

export const Slide = memo(
  ({
    output,
    cellId,
    status,
    interrupted,
    staleInputs,
    runStartTimestamp,
  }: SlideContentProps) => {
    const loading = outputIsLoading(status);
    // Use outputIsStale (like the vertical layout) so streaming output isn't
    // greyed out while the cell is still running.
    const stale = outputIsStale(
      { status, output, interrupted, runStartTimestamp, staleInputs },
      false,
    );
    return (
      <OutputArea
        className="contents"
        allowExpand={false}
        output={output}
        cellId={cellId}
        stale={stale}
        loading={loading}
      />
    );
  },
);
Slide.displayName = "Slide";
