/* Copyright 2026 Marimo. All rights reserved. */
import React, { useMemo, useRef, useState } from "react";
import { useAtomValue } from "jotai";
import { numColumnsAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import type { ICellRendererProps } from "../types";
import type { SlideType, SlidesLayout } from "./types";
import { SlidesMinimap } from "@/components/slides/minimap";
import useEvent from "react-use-event-hook";
import type { RevealApi } from "reveal.js";

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
  const deckRef = useRef<RevealApi | null>(null);

  const { cellsWithOutput, skippedIds, slideTypes, defaultIndex } =
    useMemo(() => {
      const withOutput = cells.filter(
        (cell) => cell.output != null && cell.output.data !== "",
      );
      const skipped = new Set<CellId>();
      const types = new Map<CellId, SlideType>();
      for (const c of withOutput) {
        const type = layout.cells.get(c.id)?.type;
        if (type) {
          types.set(c.id, type);
        }
        if (type === "skip") {
          skipped.add(c.id);
        }
      }
      // Prefer a non-skipped cell on initial load so the deck lands on a real
      // slide instead of the skip-preview overlay.
      const firstNonSkippedIndex = withOutput.findIndex(
        (c) => !skipped.has(c.id),
      );
      const defaultIdx = firstNonSkippedIndex === -1 ? 0 : firstNonSkippedIndex;
      return {
        cellsWithOutput: withOutput,
        skippedIds: skipped,
        slideTypes: types,
        defaultIndex: defaultIdx,
      };
    }, [cells, layout.cells]);

  const activeSlideIndex = activeCellId
    ? cellsWithOutput.findIndex((c) => c.id === activeCellId)
    : defaultIndex;
  const resolvedIndex =
    activeSlideIndex === -1 ? defaultIndex : activeSlideIndex;

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
      deckRef={deckRef}
      configWidth={250}
      mode={mode}
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
        activeCellId={activeCellId ?? cellsWithOutput[defaultIndex]?.id ?? null}
        skippedIds={skippedIds}
        slideTypes={slideTypes}
        onSlideClick={handleSlideChange}
      />
      {slides}
    </div>
  );
};
