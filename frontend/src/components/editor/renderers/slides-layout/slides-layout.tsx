/* Copyright 2024 Marimo. All rights reserved. */
import React, { memo } from "react";
import type { ICellRendererProps } from "../types";
import type { SlidesLayout } from "./types";

import type { CellId } from "@/core/cells/ids";
import type { CellRuntimeState } from "@/core/cells/types";
import type { AppMode } from "@/core/mode";
import { OutputArea } from "../../Output";

type Props = ICellRendererProps<SlidesLayout>;

const LazySlidesComponent = React.lazy(
  () => import("../../../slides/slides-component"),
);

export const SlidesLayoutRenderer: React.FC<Props> = ({
  // Currently we don't have layout config
  // layout,
  // setLayout,
  cells,
  mode,
}) => {
  const isReading = mode === "read";

  const slides = (
    <LazySlidesComponent forceKeyboardNavigation={true}>
      {cells.map((cell) => {
        const isOutputEmpty = cell.output == null || cell.output.data === "";
        if (isOutputEmpty) {
          return null;
        }
        return (
          <Slide
            key={cell.id}
            cellId={cell.id}
            code={cell.code}
            status={cell.status}
            output={cell.output}
            mode={mode}
          />
        );
      })}
    </LazySlidesComponent>
  );

  if (isReading) {
    return <div className="p-4">{slides}</div>;
  }

  return <div className="pr-9">{slides}</div>;
};

interface SlideProps extends Pick<CellRuntimeState, "output" | "status"> {
  className?: string;
  code: string;
  cellId: CellId;
  mode: AppMode;
}

const Slide = memo(({ output, cellId, status }: SlideProps) => {
  const loading = status === "running" || status === "queued";
  return (
    <OutputArea
      className="contents"
      allowExpand={false}
      output={output}
      cellId={cellId}
      stale={loading}
    />
  );
});
Slide.displayName = "Slide";
