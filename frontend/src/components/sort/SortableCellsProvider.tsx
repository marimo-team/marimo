/* Copyright 2024 Marimo. All rights reserved. */

import {
  type AutoScrollOptions,
  type CollisionDetection,
  closestCenter,
  DndContext,
  type DragEndEvent,
  type DragStartEvent,
  getFirstCollision,
  KeyboardSensor,
  PointerSensor,
  pointerWithin,
  rectIntersection,
  type UniqueIdentifier,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { restrictToVerticalAxis } from "@dnd-kit/modifiers";
import { sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import React, { useCallback, useMemo, useState } from "react";
import type { CellId } from "@/core/cells/ids";
import { useAppConfig } from "@/core/config/config";
import { Arrays } from "@/utils/arrays";
import type { CellColumnId, MultiColumn } from "@/utils/id-tree";
import { invariant } from "@/utils/invariant";
import { getNotebook, useCellActions } from "../../core/cells/cells";
import { useEvent } from "../../hooks/useEvent";

interface SortableCellsProviderProps {
  multiColumn: boolean;
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
  multiColumn,
}: SortableCellsProviderProps) => {
  const { dropCellOverCell, dropCellOverColumn, moveColumn, compactColumns } =
    useCellActions();

  const [activeId, setActiveId] = useState<UniqueIdentifier | null>(null);
  const [clonedItems, setClonedItems] = useState<MultiColumn<CellId> | null>(
    null,
  );

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

  const handleDragStart = useEvent((event: DragStartEvent) => {
    setActiveId(event.active.id);
    const notebook = getNotebook();
    setClonedItems(notebook.cellIds);
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

  /**
   * Custom collision detection:
   * 1. If dragging a column, we can only drop on other columns
   *  - We just use closestCenter
   *  - We filter the droppableContainers to only consider other columns
   * 2. If dragging a cell, we want to find the best column to drop on
   *  - We get the first intersection
   *  - Find the closest column to the cell
   *  - If the column is empty, we consider it a valid drop target
   *  - Otherwise, we only consider the cells in the same column
   */
  const collisionDetectionStrategy = useCallback(
    (args: Parameters<CollisionDetection>[0]) => {
      const columnContainers = args.droppableContainers.filter((container) =>
        isColumnId(container.id),
      );

      // 1. Handle column dragging
      if (activeId && isColumnId(activeId)) {
        return closestCenter({
          ...args,
          droppableContainers: columnContainers,
        });
      }

      // 2. Handle cell dragging

      // Get the first column intersection
      const pointerIntersections = pointerWithin({
        ...args,
        droppableContainers: columnContainers,
      });
      const intersections =
        pointerIntersections.length > 0
          ? pointerIntersections
          : rectIntersection({
              ...args,
              droppableContainers: columnContainers,
            });
      const overId = getFirstCollision(intersections, "id");
      if (!overId) {
        return [];
      }
      invariant(isColumnId(overId), `Expected column id. Got: ${overId}`);

      // If column is empty, we can drop on it
      const notebook = getNotebook();
      const column = notebook.cellIds.get(overId);
      invariant(column, `Expected column. Got: ${overId}`);
      if (column && column.topLevelIds.length === 0) {
        // Return the column
        return [{ id: overId }];
      }

      // If the column is not empty, we only consider the cells in the same column
      const cellIdSet = new Set(column.topLevelIds);
      const collisions = closestCenter({
        ...args,
        droppableContainers: args.droppableContainers.filter(
          (container) =>
            container.id !== overId && cellIdSet.has(container.id as CellId),
        ),
      });

      if (collisions.length > 0) {
        const overId = collisions[0].id;
        invariant(isCellId(overId), `Expected cell id. Got: ${overId}`);
        // Return the cell
        return [{ id: overId }];
      }

      return [];
    },
    [activeId],
  );

  const handleDragOver = useEvent(({ active, over }) => {
    const overId = over?.id;

    if (overId == null || active.id === overId) {
      return;
    }

    // Handle moving cells
    if (isCellId(active.id)) {
      // Moving a cell to a column
      if (isColumnId(overId)) {
        dropCellOverColumn({
          cellId: active.id,
          columnId: overId,
        });
        return;
      }

      // Moving a cell above another cell
      if (isCellId(overId)) {
        dropCellOverCell({
          cellId: active.id,
          overCellId: overId,
        });
        return;
      }
    }

    // Moving a column to another column
    if (isColumnId(active.id) && isColumnId(overId)) {
      moveColumn({
        column: active.id,
        overColumn: overId,
      });
    }
  });

  const handleDragEnd = useEvent((event: DragEndEvent) => {
    const { active, over } = event;

    if (over === null || active.id === over.id) {
      return;
    }

    compactColumns();
  });

  return (
    <DndContext
      autoScroll={autoScroll}
      sensors={sensors}
      // For single-column, we just do closestCenter
      collisionDetection={
        multiColumn ? collisionDetectionStrategy : closestCenter
      }
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
  return typeof id === "string" && !id.startsWith("tree_");
}

function isColumnId(id: UniqueIdentifier): id is CellColumnId {
  return typeof id === "string" && id.startsWith("tree_");
}
