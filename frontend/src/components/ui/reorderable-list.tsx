/* Copyright 2024 Marimo. All rights reserved. */

import type React from "react";
import { useEffect, useMemo, useState } from "react";
import { ListBox, ListBoxItem, useDragAndDrop } from "react-aria-components";
import { useListData } from "react-stately";
import {
  ContextMenu,
  ContextMenuCheckboxItem,
  ContextMenuContent,
  ContextMenuTrigger,
} from "./context-menu";
import "./reorderable-list.css";

export interface ReorderableListProps<T extends { id: string | number }> {
  /**
   * The current list of items
   */
  value: T[];
  /**
   * Callback when items are reordered
   */
  setValue: (items: T[]) => void;
  /**
   * Render function for each item
   */
  renderItem: (item: T) => React.ReactNode;
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
}

/**
 * A generic reorderable list component using react-aria-components and react-stately.
 * Items can be reordered via drag and drop.
 *
 * @example
 * ```tsx
 * interface MyItem {
 *   id: string;
 *   name: string;
 * }
 *
 * const [items, setItems] = useState<MyItem[]>([...]);
 *
 * <ReorderableList
 *   value={items}
 *   setValue={setItems}
 *   renderItem={(item) => <div>{item.name}</div>}
 *   ariaLabel="My reorderable list"
 * />
 * ```
 */
export function ReorderableList<T extends { id: string | number }>({
  value,
  setValue,
  renderItem,
  availableItems,
  getItemLabel = (item) => String(item.id),
  minItems = 1,
  ariaLabel = "Reorderable list",
  className,
}: ReorderableListProps<T>) {
  const list = useListData({
    initialItems: value,
    getKey: (item) => item.id,
  });

  const [needsSync, setNeedsSync] = useState(false);

  // Sync external value changes to internal list state
  // useEffect(() => {
  //   // Only update if the items have actually changed
  //   if (isEqual(list.items, value)) {
  //     return;
  //   }

  //   list.setSelectedKeys(new Set());
  //   list.remove(...list.items.map((item) => item.id));
  //   for (const item of value) {
  //     list.append(item);
  //   }
  // }, [value, list]);

  const { dragAndDropHooks } = useDragAndDrop<T>({
    getItems: (_keys, items) =>
      items.map((item) => {
        return { "text/plain": String(item.id) };
      }),
    onReorder(e) {
      if (e.target.dropPosition === "before") {
        list.moveBefore(e.target.key, e.keys);
      } else if (e.target.dropPosition === "after") {
        list.moveAfter(e.target.key, e.keys);
      }
      setNeedsSync(true);
    },
  });

  // Calling this in the onReorder callback does not work since
  // the reordering is not complete yet.
  useEffect(() => {
    if (!needsSync) {
      return;
    }
    setNeedsSync(false);
    setValue(list.items);
  }, [list.items, setValue, needsSync, setNeedsSync]);

  // Track which items are currently in the list
  const currentItemIds = useMemo(
    () => new Set(value.map((item) => item.id)),
    [value],
  );

  const handleToggleItem = (item: T, isChecked: boolean) => {
    if (isChecked) {
      // Add item to the list
      list.append(item);
    } else {
      // Remove item from the list (only if we're above minItems)
      if (value.length > minItems) {
        list.remove(item.id);
      }
    }
    setNeedsSync(true);
  };

  const listBox = (
    <ListBox
      aria-label={ariaLabel}
      selectionMode="single"
      items={list.items}
      dragAndDropHooks={dragAndDropHooks}
      className={className}
    >
      {(item) => (
        <ListBoxItem className="active:cursor-grabbing data-[dragging]:opacity-60">
          {renderItem(item)}
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
          const isChecked = currentItemIds.has(item.id);
          const isDisabled = isChecked && value.length <= minItems;

          return (
            <ContextMenuCheckboxItem
              key={item.id}
              checked={isChecked}
              disabled={isDisabled}
              onCheckedChange={(checked) => {
                handleToggleItem(item, checked === true);
              }}
            >
              {getItemLabel(item)}
            </ContextMenuCheckboxItem>
          );
        })}
      </ContextMenuContent>
    </ContextMenu>
  );
}
