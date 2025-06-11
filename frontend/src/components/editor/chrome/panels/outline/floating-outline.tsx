/* Copyright 2024 Marimo. All rights reserved. */
import { notebookOutline } from "@/core/cells/cells";
import { cn } from "@/utils/cn";
import { useAtomValue } from "jotai";
import React from "react";
import {
  useActiveOutline,
  scrollToOutlineItem,
  findOutlineElements,
} from "./useActiveOutline";
import type { OutlineItem } from "@/core/cells/outline";

export const FloatingOutline: React.FC = () => {
  const { items } = useAtomValue(notebookOutline);
  const { activeHeaderId, activeOccurrences } = useActiveOutline(
    findOutlineElements(items),
  );
  const [isHovered, setIsHovered] = React.useState(false);

  // Hide if < 2 items
  // It's kinda useless to have an outline with only one item
  // and Notion does the same
  if (items.length < 2) {
    return null;
  }

  return (
    <div
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className={cn(
        "fixed top-[25vh] right-8 z-[10000]",
        // Hide on small screens
        "hidden md:block",
      )}
    >
      <OutlineList
        className={cn(
          "-top-4 max-h-[70vh] bg-background rounded-lg shadow-lg absolute overflow-auto transition-all duration-300 w-[300px] border",
          isHovered ? "-left-[280px] opacity-100" : "left-[300px] opacity-0",
        )}
        items={items}
        activeHeaderId={activeHeaderId}
        activeOccurrences={activeOccurrences}
      />
      <MiniMap
        items={items}
        activeHeaderId={activeHeaderId}
        activeOccurrences={activeOccurrences}
      />
    </div>
  );
};

export const MiniMap: React.FC<{
  items: OutlineItem[];
  activeHeaderId: string | undefined;
  activeOccurrences: number | undefined;
}> = ({ items, activeHeaderId, activeOccurrences }) => {
  // Map of selector to its occurrences
  const seen = new Map<string, number>();
  return (
    <div className="flex flex-col gap-4 items-end max-h-[70vh] overflow-hidden">
      {items.map((item, idx) => {
        const identifier = "id" in item.by ? item.by.id : item.by.path;
        // Keep track of how many times we've seen this selector
        const occurrences = seen.get(identifier) ?? 0;
        seen.set(identifier, occurrences + 1);

        return (
          <div
            key={`${identifier}-${idx}`}
            className={cn(
              "h-[2px] bg-muted-foreground/60",
              item.level === 1 && "w-5",
              item.level === 2 && "w-4",
              item.level === 3 && "w-3",
              item.level === 4 && "w-2",
              occurrences === activeOccurrences &&
                activeHeaderId === identifier &&
                "bg-foreground",
            )}
            onClick={() => scrollToOutlineItem(item, occurrences)}
          />
        );
      })}
    </div>
  );
};

export const OutlineList: React.FC<{
  className?: string;
  items: OutlineItem[];
  activeHeaderId: string | undefined;
  activeOccurrences: number | undefined;
}> = ({ items, activeHeaderId, activeOccurrences, className }) => {
  // Map of selector to its occurrences
  const seen = new Map<string, number>();
  return (
    <div className={cn("flex flex-col overflow-auto py-4 pl-2", className)}>
      {items.map((item, idx) => {
        const identifier = "id" in item.by ? item.by.id : item.by.path;
        // Keep track of how many times we've seen this selector
        const occurrences = seen.get(identifier) ?? 0;
        seen.set(identifier, occurrences + 1);

        return (
          <div
            key={`${identifier}-${idx}`}
            className={cn(
              "px-2 py-1 cursor-pointer hover:bg-accent/50 hover:text-accent-foreground rounded-l",
              item.level === 1 && "font-semibold",
              item.level === 2 && "ml-3",
              item.level === 3 && "ml-6",
              item.level === 4 && "ml-9",
              occurrences === activeOccurrences &&
                activeHeaderId === identifier &&
                "text-accent-foreground",
            )}
            onClick={() => scrollToOutlineItem(item, occurrences)}
          >
            {item.name}
          </div>
        );
      })}
    </div>
  );
};
