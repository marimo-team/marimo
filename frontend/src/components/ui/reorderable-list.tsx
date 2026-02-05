/* Copyright 2026 Marimo. All rights reserved. */

import type React from "react";
import { useMemo } from "react";
import {
  type DropItem,
  ListBox,
  ListBoxItem,
  useDragAndDrop,
} from "react-aria-components";
import { Logger } from "@/utils/Logger";
import {
  ContextMenu,
  ContextMenuCheckboxItem,
  ContextMenuContent,
  ContextMenuTrigger,
} from "./context-menu";
import "./reorderable-list.css";

interface DragData<T> {
  itemId: string;
  sourceListId: string;
  item: T;
}

function getDragMimeType(dragType: string): string {
  return `application/x-reorderable-${dragType}`;
}

function parseDragData<T>(text: string): DragData<T> | null {
  try {
    return JSON.parse(text) as DragData<T>;
  } catch {
    return null;
  }
}

export interface ReorderableListProps<T> {
  /**
   * The current list of items.
   */
  value: T[];
  /**
   * Callback when items are reordered
   */
  setValue: (items: T[]) => void;
  /**
   * Function to get a unique key for each item. Used for drag-drop and rendering.
   */
  getKey: (item: T) => string;
  /**
   * Render function for each item.
   * Note: Avoid interactive elements (buttons) inside - they break drag behavior.
   */
  renderItem: (item: T) => React.ReactNode;
  /**
   * Callback when an item is clicked
   */
  onAction?: (item: T) => void;
  /**
   * All available items that can be added to the list
   */
  availableItems?: T[];
  /**
   * Function to get the label for an item in the context menu
   */
  getItemLabel?: (item: T) => React.ReactNode;
  /**
   * Minimum number of items that must remain in the list (default: 1)
   */
  minItems?: number;
  /**
   * Aria label for accessibility
   */
  ariaLabel?: string;
  /**
   * Additional class name for the list container
   */
  className?: string;
  /**
   * Configuration for cross-list drag-drop. When set, items can be dragged
   * between lists that share the same `dragType`.
   */
  crossListDrag?: {
    /** Identifier that links lists together - same dragType = can share items */
    dragType: string;
    /** Unique identifier for this list */
    listId: string;
    /**
     * Callback when an item is received from another list.
     * At this point, setValue has been called with the new item included,
     * but the parent component may not have re-rendered yet.
     * Use this to remove the item from the source list and handle any side effects.
     */
    onReceive: (item: T, fromListId: string, insertIndex: number) => void;
  };
}

/**
 * A generic reorderable list component using react-aria-components.
 * Items can be reordered via drag and drop within the list.
 *
 * For cross-list drag-drop, set the same `dragType` on multiple lists
 * and provide an `onReceive` callback to handle items dropped from other lists.
 *
 * @example
 * ```tsx
 * // Single list reordering
 * <ReorderableList
 *   value={items}
 *   setValue={setItems}
 *   getKey={(item) => item.id}
 *   renderItem={(item) => <div>{item.name}</div>}
 * />
 *
 * // Cross-list drag-drop
 * <ReorderableList
 *   value={sidebarItems}
 *   setValue={setSidebarItems}
 *   getKey={(item) => item.type}
 *   renderItem={(item) => <div>{item.name}</div>}
 *   crossListDrag={{
 *     dragType: "panels",
 *     listId: "sidebar",
 *     onReceive: (item, fromListId) => {
 *       // Remove from source list
 *       setOtherItems(prev => prev.filter(i => i.type !== item.type));
 *     },
 *   }}
 * />
 * ```
 */
export const ReorderableList = <T extends object>({
  value,
  setValue,
  getKey,
  renderItem,
  onAction,
  availableItems,
  getItemLabel,
  minItems = 1,
  ariaLabel = "Reorderable list",
  className,
  crossListDrag,
}: ReorderableListProps<T>) => {
  const mimeType = crossListDrag
    ? getDragMimeType(crossListDrag.dragType)
    : null;
  const onReceive = crossListDrag?.onReceive;

  // Shared handler for cross-list drops
  const handleCrossListDrop = async (
    items: DropItem[],
    insertIndex: number,
  ) => {
    if (!mimeType || !crossListDrag?.listId || !onReceive) {
      return;
    }

    for (const dragItem of items) {
      if (dragItem.kind !== "text" || !dragItem.types.has(mimeType)) {
        continue;
      }

      const text = await dragItem.getText(mimeType);
      const data = parseDragData<T>(text);
      if (!data) {
        continue;
      }

      // Only accept drops from different lists
      if (data.sourceListId === crossListDrag.listId) {
        continue;
      }

      // Skip if item already exists in this list
      if (value.some((item) => getKey(item) === getKey(data.item))) {
        continue;
      }

      // Add to this list and notify parent
      setValue([
        ...value.slice(0, insertIndex),
        data.item,
        ...value.slice(insertIndex),
      ]);
      onReceive(data.item, data.sourceListId, insertIndex);
    }
  };

  const { dragAndDropHooks } = useDragAndDrop<T>({
    getItems: (keys) =>
      [...keys].map((key) => {
        const item = value.find((i) => getKey(i) === key);
        const baseData: Record<string, string> = {
          "text/plain": String(key),
        };

        // Add cross-list drag data if dragType is set
        if (mimeType && crossListDrag?.listId && item) {
          const dragData: DragData<T> = {
            itemId: String(key),
            sourceListId: crossListDrag.listId,
            item,
          };
          baseData[mimeType] = JSON.stringify(dragData);
        }

        return baseData;
      }),

    // Accept drops from lists with the same dragType
    acceptedDragTypes: mimeType ? [mimeType, "text/plain"] : ["text/plain"],

    onReorder(e) {
      const keySet = new Set(e.keys);
      const draggedItems = value.filter((item) => keySet.has(getKey(item)));
      const remaining = value.filter((item) => !keySet.has(getKey(item)));

      const targetIndex = remaining.findIndex(
        (item) => getKey(item) === e.target.key,
      );
      const insertIndex =
        e.target.dropPosition === "before" ? targetIndex : targetIndex + 1;

      setValue([
        ...remaining.slice(0, insertIndex),
        ...draggedItems,
        ...remaining.slice(insertIndex),
      ]);
    },

    // Handle drops from other lists (on a specific item)
    async onInsert(e) {
      const targetIndex = value.findIndex(
        (item) => getKey(item) === e.target.key,
      );
      const insertIndex =
        e.target.dropPosition === "before" ? targetIndex : targetIndex + 1;
      await handleCrossListDrop(e.items, insertIndex);
    },

    // Handle drops on empty list or root
    async onRootDrop(e) {
      await handleCrossListDrop(e.items, value.length);
    },
  });

  // Track which items are currently in the list
  const currentItemKeys = useMemo(
    () => new Set(value.map((item) => getKey(item))),
    [value, getKey],
  );

  const handleToggleItem = (item: T, isChecked: boolean) => {
    if (isChecked) {
      setValue([...value, item]);
    } else if (value.length > minItems) {
      setValue(value.filter((v) => getKey(v) !== getKey(item)));
    }
  };

  const handleAction = (key: React.Key) => {
    if (!onAction) {
      return;
    }

    const item = value.find((i) => getKey(i) === key);

    if (!item) {
      Logger.warn("handleAction: item not found for key", {
        key,
        availableKeys: value.map((v) => getKey(v)),
      });
      return;
    }

    onAction(item);
  };

  // When list is empty, show a drop zone placeholder
  const isEmpty = value.length === 0;

  const listBox = (
    <ListBox
      aria-label={ariaLabel}
      selectionMode="none"
      dragAndDropHooks={dragAndDropHooks}
      className={className}
      onAction={handleAction}
    >
      {value.map((item) => (
        <ListBoxItem
          key={getKey(item)}
          id={getKey(item)}
          className="active:cursor-grabbing data-[dragging]:opacity-60 outline-none"
        >
          {renderItem(item)}
        </ListBoxItem>
      ))}
      {/*
       * When the list is empty, render an invisible placeholder item.
       * This ensures the ListBox maintains minimum dimensions so users can:
       * 1. Right-click to access the context menu and add items back
       * 2. Drag items from another list into this empty list
       */}
      {isEmpty && (
        <ListBoxItem id="__empty__" className="min-h-[40px] min-w-[40px]">
          <span />
        </ListBoxItem>
      )}
    </ListBox>
  );

  // Only show context menu if availableItems is provided
  if (!availableItems) {
    return listBox;
  }

  return (
    <ContextMenu>
      <ContextMenuTrigger asChild={true}>{listBox}</ContextMenuTrigger>
      <ContextMenuContent>
        {availableItems.map((item) => {
          const key = getKey(item);
          const isChecked = currentItemKeys.has(key);
          const isDisabled = isChecked && value.length <= minItems;

          return (
            <ContextMenuCheckboxItem
              key={key}
              checked={isChecked}
              disabled={isDisabled}
              onCheckedChange={(checked) => {
                handleToggleItem(item, checked);
              }}
            >
              {getItemLabel ? getItemLabel(item) : key}
            </ContextMenuCheckboxItem>
          );
        })}
      </ContextMenuContent>
    </ContextMenu>
  );
};
