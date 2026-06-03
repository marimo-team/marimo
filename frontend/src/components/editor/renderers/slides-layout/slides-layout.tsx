/* Copyright 2026 Marimo. All rights reserved. */
import React, { useMemo, useState } from "react";
import { useAtomValue } from "jotai";
import { numColumnsAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { kioskModeAtom } from "@/core/mode";
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
  // Kiosk clients (e.g. reveal.js's speaker-view iframes) are read-only and
  // shouldn't show authoring chrome, so we collapse to the read-mode layout.
  const kioskMode = useAtomValue(kioskModeAtom);
  const isReading = mode === "read" || kioskMode;
  const numColumns = useAtomValue(numColumnsAtom);
  const isMultiColumn = numColumns > 1;
  const [activeCellId, setActiveCellId] = useState<CellId | null>(null);

  const { slideCells, skippedIds, noOutputIds, slideTypes, startCellIndex } =
    useMemo(() => computeSlideCellsInfo(cells, layout), [cells, layout]);

  const activeSlideIndex = activeCellId
    ? slideCells.findIndex((c) => c.id === activeCellId)
    : startCellIndex;
  const resolvedIndex =
    activeSlideIndex === -1 ? startCellIndex : activeSlideIndex;

  const handleSlideChange = useEvent((index: number) => {
    const cell = slideCells[index];
    if (cell) {
      setActiveCellId(cell.id);
    }
  });

  const slides = (
    <LazySlidesComponent
      slideCells={slideCells}
      layout={layout}
      setLayout={setLayout}
      noOutputIds={noOutputIds}
      activeIndex={resolvedIndex}
      onSlideChange={handleSlideChange}
      configWidth={280}
      mode={isReading ? "read" : mode}
      isEditable={!isReading}
    />
  );

  if (isReading) {
    // In kiosk mode (e.g. reveal.js's speaker-view iframes), anchor to the
    // iframe viewport with `dvh`/`dvw` so the deck resizes with the popup
    // window. The non-kiosk read mode keeps its 16:9 cap so the deck doesn't
    // balloon to the full viewport on wide screens.
    if (kioskMode) {
      return (
        <div className="flex h-dvh w-dvw overflow-hidden bg-background">
          {slides}
        </div>
      );
    }
    return (
      <div className="p-4 flex flex-1 items-center justify-center min-h-0">
        <div className="h-full max-h-[95vh] aspect-video max-w-full flex">
          {slides}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 pr-18 pb-2 flex flex-row gap-2 min-h-0">
      <SlidesMinimap
        cells={slideCells}
        thumbnailWidth={220}
        canReorder={!isMultiColumn}
        activeCellId={activeCellId ?? slideCells[startCellIndex]?.id ?? null}
        skippedIds={skippedIds}
        noOutputIds={noOutputIds}
        slideTypes={slideTypes}
        onSlideClick={handleSlideChange}
      />
      {slides}
    </div>
  );
};
