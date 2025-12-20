/* Copyright 2024 Marimo. All rights reserved. */

import type React from "react";
import { useMemo } from "react";
import { ListBox, ListBoxItem, useDragAndDrop } from "react-aria-components";
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
  const { dragAndDropHooks } = useDragAndDrop<T>({
    getItems: (keys) => [...keys].map((key) => ({ "text/plain": String(key) })),
    onReorder(e) {
      const keySet = new Set(e.keys);
      const draggedItems = value.filter((item) => keySet.has(item.id));
      const remaining = value.filter((item) => !keySet.has(item.id));

      const targetIndex = remaining.findIndex(
        (item) => item.id === e.target.key,
      );
      const insertIndex =
        e.target.dropPosition === "before" ? targetIndex : targetIndex + 1;

      setValue([
        ...remaining.slice(0, insertIndex),
        ...draggedItems,
        ...remaining.slice(insertIndex),
      ]);
    },
  });

  // Track which items are currently in the list
  const currentItemIds = useMemo(
    () => new Set(value.map((item) => item.id)),
    [value],
  );

  const handleToggleItem = (item: T, isChecked: boolean) => {
    if (isChecked) {
      setValue([...value, item]);
    } else if (value.length > minItems) {
      setValue(value.filter((v) => v.id !== item.id));
    }
  };

  const listBox = (
    <ListBox
      aria-label={ariaLabel}
      selectionMode="single"
      items={value}
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
                handleToggleItem(item, checked);
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
