/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  DragEndEvent,
  useSensors,
} from "@dnd-kit/core";
import { restrictToVerticalAxis } from "@dnd-kit/modifiers";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { useCellActions, useNotebook } from "../../core/cells/cells";
import { useEvent } from "../../hooks/useEvent";
import { CellId } from "@/core/cells/ids";

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

  const ids = notebook.cellIds;

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

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      modifiers={[restrictToVerticalAxis]}
      onDragEnd={handleDragEnd}
    >
      <SortableContext
        items={ids}
        disabled={disabled}
        strategy={verticalListSortingStrategy}
      >
        {children}
      </SortableContext>
    </DndContext>
  );
};

export const SortableCellsProvider = React.memo(SortableCellsProviderInternal);
