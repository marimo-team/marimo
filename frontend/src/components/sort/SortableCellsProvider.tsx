/* Copyright 2023 Marimo. All rights reserved. */
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
import { useCellActions, useCells } from "../../core/state/cells";
import { useEvent } from "../../hooks/useEvent";
import { CellId } from "@/core/model/ids";

interface SortableCellsProviderProps {
  children: React.ReactNode;
  disabled?: boolean;
}

const SortableCellsProviderInternal = ({
  children,
  disabled,
}: SortableCellsProviderProps) => {
  const cells = useCells();
  const { dropCellOver } = useCellActions();

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const ids = cells.present.map((item) => item.key.toString());

  const handleDragEnd = useEvent((event: DragEndEvent) => {
    const { active, over } = event;
    if (over === null) {
      return;
    }
    if (active.id === over.id) {
      return;
    }
    dropCellOver(active.id as CellId, over.id as CellId);
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
