/* Copyright 2026 Marimo. All rights reserved. */
import React, { useMemo, useState } from "react";
import { useAtomValue } from "jotai";
import { numColumnsAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import type { ICellRendererProps } from "../types";
import type { SlidesLayout } from "./types";
import { computeSlideCellsInfo } from "./compute-slide-cells";
import { SlidesMinimap } from "@/components/slides/minimap";
import useEvent from "react-use-event-hook";

type Props = ICellRendererProps<SlidesLayout>;

const LazySlidesComponent = React.lazy(
  () => import("../../../slides/reveal-component"),
);

export const SlidesLayoutRenderer: React.FC<Props> = ({
  layout,
  setLayout,
  cells,
  mode,
}) => {
  const isReading = mode === "read";
  const numColumns = useAtomValue(numColumnsAtom);
  const isMultiColumn = numColumns > 1;
  const [activeCellId, setActiveCellId] = useState<CellId | null>(null);

  const { cellsWithOutput, skippedIds, slideTypes, startCellIndex } = useMemo(
    () => computeSlideCellsInfo(cells, layout),
    [cells, layout],
  );

  const activeSlideIndex = activeCellId
    ? cellsWithOutput.findIndex((c) => c.id === activeCellId)
    : startCellIndex;
  const resolvedIndex =
    activeSlideIndex === -1 ? startCellIndex : activeSlideIndex;

  const handleSlideChange = useEvent((index: number) => {
    const cell = cellsWithOutput[index];
    if (cell) {
      setActiveCellId(cell.id);
    }
  });

  const slides = (
    <LazySlidesComponent
      cellsWithOutput={cellsWithOutput}
      layout={layout}
      setLayout={setLayout}
      activeIndex={resolvedIndex}
      onSlideChange={handleSlideChange}
      configWidth={300}
      mode={mode}
      isEditable={mode !== "read"}
    />
  );

  if (isReading) {
    // Cap the deck height and derive width from height via aspect-video so it stays 16:9 without
    // ballooning to the full viewport on wide screens.
    return (
      <div className="p-4 flex flex-1 items-center justify-center min-h-0">
        <div className="h-full max-h-[95vh] aspect-video max-w-full flex">
          {slides}
        </div>
      </div>
    );
  }

  return (
    <div className="pr-18 pb-2 flex flex-row gap-2 min-h-0">
      <SlidesMinimap
        cells={cellsWithOutput}
        thumbnailWidth={220}
        canReorder={!isMultiColumn}
        activeCellId={
          activeCellId ?? cellsWithOutput[startCellIndex]?.id ?? null
        }
        skippedIds={skippedIds}
        slideTypes={slideTypes}
        onSlideClick={handleSlideChange}
      />
      {slides}
    </div>
  );
};
