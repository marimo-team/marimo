/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  type DragEndEvent,
  useSensors,
} from "@dnd-kit/core";
import { restrictToVerticalAxis } from "@dnd-kit/modifiers";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  rectSortingStrategy,
} from "@dnd-kit/sortable";
import { useCellActions, useNotebook } from "../../core/cells/cells";
import { useEvent } from "../../hooks/useEvent";
import type { CellId } from "@/core/cells/ids";

interface SortableCellsProviderProps {
  children: React.ReactNode;
  disabled?: boolean;
}

const SortableCellsProviderInternal = ({
  children,
  disabled,
}: SortableCellsProviderProps) => {
  const notebook = useNotebook();
  const { dropCellOver } = useCellActions();

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        // to support click and drag on the same element
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  const ids = notebook.cellIds.topLevelIds;

  const handleDragEnd = useEvent((event: DragEndEvent) => {
    const { active, over } = event;
    if (over === null) {
      return;
    }
    if (active.id === over.id) {
      return;
    }
    dropCellOver({
      cellId: active.id as CellId,
      overCellId: over.id as CellId,
    });
  });

  // autoScroll threshold x: 0 is required to disable horizontal scroll
  //            threshold y: 0.1 means scroll y when near bottom/top 10% of
  //            scrollable container
  return (
    <DndContext
      autoScroll={{ threshold: { x: 0.1, y: 0.1 } }}
      sensors={sensors}
      collisionDetection={closestCenter}
      modifiers={[restrictToVerticalAxis]}
      onDragEnd={handleDragEnd}
    >
      <SortableContext
        items={ids}
        disabled={disabled}
        strategy={rectSortingStrategy}
      >
        {children}
      </SortableContext>
    </DndContext>
  );
};

export const SortableCellsProvider = React.memo(SortableCellsProviderInternal);
