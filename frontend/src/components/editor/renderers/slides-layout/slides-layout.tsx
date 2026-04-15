/* Copyright 2026 Marimo. All rights reserved. */
import React, { useState } from "react";
import { useAtomValue } from "jotai";
import { numColumnsAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import type { ICellRendererProps } from "../types";
import type { SlidesLayout } from "./types";
import { SlidesMinimap } from "@/components/slides/minimap";
import { Slide } from "@/components/slides/slide";
import useEvent from "react-use-event-hook";

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
  const numColumns = useAtomValue(numColumnsAtom);
  const isMultiColumn = numColumns > 1;
  const [activeCellId, setActiveCellId] = useState<CellId | null>(null);

  const cellsWithOutput = cells.filter(
    (cell) => cell.output != null && cell.output.data !== "",
  );

  const activeSlideIndex = activeCellId
    ? cellsWithOutput.findIndex((c) => c.id === activeCellId)
    : 0;
  const resolvedIndex = activeSlideIndex === -1 ? 0 : activeSlideIndex;

  const handleSlideChange = useEvent((index: number) => {
    const cell = cellsWithOutput[index];
    if (cell) {
      setActiveCellId(cell.id);
    }
  });

  const slides = (
    <LazySlidesComponent
      forceKeyboardNavigation={true}
      className="flex-1 self-center"
      activeIndex={resolvedIndex}
      onActiveIndexChange={handleSlideChange}
    >
      {cellsWithOutput.map((cell) => (
        <Slide
          key={cell.id}
          cellId={cell.id}
          status={cell.status}
          output={cell.output}
        />
      ))}
    </LazySlidesComponent>
  );

  if (isReading) {
    return <div className="p-4 flex flex-col flex-1 max-h-[95%]">{slides}</div>;
  }

  return (
    // Use 11/12 to ensure all content fits on the page (no overflow, scrolling required)
    <div className="pr-18 pb-5 flex-1 flex flex-row max-h-11/12 gap-2">
      <SlidesMinimap
        cells={cellsWithOutput}
        canReorder={!isMultiColumn}
        activeCellId={activeCellId ?? cellsWithOutput[0]?.id ?? null}
        onSlideClick={handleSlideChange}
      />
      {slides}
    </div>
  );
};
