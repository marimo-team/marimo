/* Copyright 2024 Marimo. All rights reserved. */
import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  type DragEndEvent,
  useSensors,
  type AutoScrollOptions,
  type UniqueIdentifier,
  type DragStartEvent,
  useDroppable,
} from "@dnd-kit/core";
import { restrictToVerticalAxis } from "@dnd-kit/modifiers";
import { sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import { useCellActions, useNotebook } from "../../core/cells/cells";
import { useEvent } from "../../hooks/useEvent";
import type { CellId } from "@/core/cells/ids";
import { useAppConfig } from "@/core/config/config";
import { Arrays } from "@/utils/arrays";
import type { CellColumnId, MultiColumn } from "@/utils/id-tree";
import { SquarePlusIcon } from "lucide-react";

interface SortableCellsProviderProps {
  children: React.ReactNode;
}

// autoScroll threshold x: 0 is required to disable horizontal scroll
//            threshold y: 0.1 means scroll y when near bottom/top 10% of
//            scrollable container
const autoScroll: AutoScrollOptions = {
  threshold: { x: 0, y: 0.1 },
};

const SortableCellsProviderInternal = ({
  children,
}: SortableCellsProviderProps) => {
  const { cellIds } = useNotebook();
  const { dropCellOverCell, dropCellOverColumn, dropOverNewColumn, moveColumn, compactColumns } =
    useCellActions();

  const [activeId, setActiveId] = useState<UniqueIdentifier | null>(null);
  const [clonedItems, setClonedItems] = useState<MultiColumn<CellId> | null>(
    null,
  );
  const alreadyCreatedNewColumn = useRef(false);

  const [config] = useAppConfig();
  const modifiers = useMemo(() => {
    if (config.width === "columns") {
      return Arrays.EMPTY;
    }
    return [restrictToVerticalAxis];
  }, [config.width]);

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

  useEffect(() => {
    requestAnimationFrame(() => {
      recentlyMovedToNewContainer.current = false;
    });
  }, [cellIds]);
  const recentlyMovedToNewContainer = useRef(false);

  const handleDragStart = useEvent((event: DragStartEvent) => {
    setActiveId(event.active.id);
    setClonedItems(cellIds);
  });

  const handleDragCancel = useEvent(() => {
    // TODO: restore cloned items
    if (clonedItems) {
      // Reset items to their original state in case items have been
      // Dragged across containers
      // setItems(clonedItems);
    }

    setActiveId(null);
    setClonedItems(null);
  });

  // See example: https://github.com/clauderic/dnd-kit/blob/master/stories/2%20-%20Presets/Sortable/MultipleContainers.tsx#L315-L372
  const handleDragOver = useEvent(({ active, over }) => {
    const overId = over?.id;
    const isCellDrag = isCellId(active.id) && isCellId(overId);
    const isColumnDrag = isColumnId(active.id) && isColumnId(overId);

    if (
      overId == null ||
      active.id === overId
    ) {
      return;
    }

    if (isCellDrag) {
      console.log("+++ isCellDrag", active.id, overId);
      dropCellOverCell({
        cellId: active.id,
        overCellId: overId,
      });
      return;
    }

    if (isColumnDrag) {
      console.log("+++ isColumnDrag", active.id, overId);
      moveColumn({
        column: active.id as CellColumnId,
        overColumn: overId,
      });
      return;
    }

    if (isCellId(active.id) && overId === PLACEHOLDER_COLUMN_ID) {
      if (alreadyCreatedNewColumn.current) {
        return;
      }
      console.log("+++ dropOverNewColumn", active.id, overId);
      dropOverNewColumn({
        cellId: active.id,
      });
      alreadyCreatedNewColumn.current = true;
      return;
    }

    if (isCellId(active.id) && isColumnId(overId)) {
      console.log("+++ dropCellOverColumn", active.id, overId);
      dropCellOverColumn({
        cellId: active.id,
        columnId: overId,
      });
      return;
    }


    // setItems((items) => {
    //   const activeItems = items[activeContainer];
    //   const overItems = items[overContainer];
    //   const overIndex = overItems.indexOf(overId);
    //   const activeIndex = activeItems.indexOf(active.id);

    //   let newIndex: number;

    //   if (overId in items) {
    //     newIndex = overItems.length + 1;
    //   } else {
    //     const isBelowOverItem =
    //       over &&
    //       active.rect.current.translated &&
    //       active.rect.current.translated.top >
    //         over.rect.top + over.rect.height;

    //     const modifier = isBelowOverItem ? 1 : 0;

    //     newIndex =
    //       overIndex >= 0 ? overIndex + modifier : overItems.length + 1;
    //   }

    //   recentlyMovedToNewContainer.current = true;

    //   return {
    //     ...items,
    //     [activeContainer]: items[activeContainer].filter(
    //       (item) => item !== active.id,
    //     ),
    //     [overContainer]: [
    //       ...items[overContainer].slice(0, newIndex),
    //       items[activeContainer][activeIndex],
    //       ...items[overContainer].slice(
    //         newIndex,
    //         items[overContainer].length,
    //       ),
    //     ],
    //   };
    // });
  });

  const handleDragEnd = useEvent((event: DragEndEvent) => {
    const { active, over } = event;
    // compactColumns();
    alreadyCreatedNewColumn.current = false;

    if (over === null || active.id === over.id) {
      return;
    }

    const isCellDrag = isCellId(active.id) && isCellId(over.id);
    const isColumnDrag = isColumnId(active.id) && isColumnId(over.id);

    // if (isCellId(active.id) && over.id === PLACEHOLDER_COLUMN_ID) {
    //   if (alreadyCreatedNewColumn.current) {
    //     return;
    //   }
    //   dropOverNewColumn({
    //     cellId: active.id,
    //   });
    //   return;
    // }

    // if (isCellDrag) {
    //   dropCellOverCell({
    //     cellId: active.id as CellId,
    //     overCellId: over.id as CellId,
    //   });
    // }

    // if (isColumnDrag) {
    //   moveColumn({
    //     column: active.id as CellColumnId,
    //     overColumn: over.id as CellColumnId,
    //   });
    // }
  });

  return (
    <DndContext
      autoScroll={autoScroll}
      sensors={sensors}
      collisionDetection={closestCenter}
      modifiers={modifiers}
      onDragEnd={handleDragEnd}
      onDragStart={handleDragStart}
      onDragCancel={handleDragCancel}
      onDragOver={handleDragOver}
    >
      {children}
    </DndContext>
  );
};

export const SortableCellsProvider = React.memo(SortableCellsProviderInternal);

function isCellId(id: UniqueIdentifier): id is CellId {
  return (
    typeof id === "string" &&
    id !== PLACEHOLDER_COLUMN_ID &&
    !id.startsWith("tree_")
  );
}

function isColumnId(id: UniqueIdentifier): id is CellColumnId {
  return typeof id === "string" && id.startsWith("tree_");
}

const PLACEHOLDER_COLUMN_ID = "__placeholder-column__";

export const PlaceholderColumn: React.FC = () => {
  const { setNodeRef, isOver } = useDroppable({
    id: PLACEHOLDER_COLUMN_ID,
  });

  return (
    <div
      ref={setNodeRef}
      className={`w-[600px] h-full border-2 border-dashed border-[var(--slate-5)] rounded-lg flex justify-center z-10 ${
        isOver ? "bg-[var(--slate-3)]" : "bg-[var(--slate-1)]"
      }`}
    >
      <p className="text-muted-foreground max-h-[50vh] flex items-center gap-2">
        <SquarePlusIcon className="w-4 h-4" />
        Drag cell to add new column
      </p>
    </div>
  );
};
