/* Copyright 2026 Marimo. All rights reserved. */

import { outputIsLoading } from "@/core/cells/cell";
import { OutputArea } from "../editor/Output";
import { memo } from "react";
import type { CellId } from "@/core/cells/ids";
import type { CellRuntimeState } from "@/core/cells/types";

interface SlideContentProps extends Pick<
  CellRuntimeState,
  "output" | "status"
> {
  cellId: CellId;
  stale: boolean;
}

export const Slide = memo(
  ({ output, cellId, status, stale }: SlideContentProps) => {
    const loading = outputIsLoading(status);
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
