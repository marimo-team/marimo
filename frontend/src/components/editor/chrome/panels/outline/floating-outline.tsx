/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import React from "react";
import { notebookOutline } from "@/core/cells/cells";
import type { OutlineItem } from "@/core/cells/outline";
import { cn } from "@/utils/cn";
import {
  findOutlineElements,
  scrollToOutlineItem,
  useActiveOutline,
} from "./useActiveOutline";

export const FloatingOutline: React.FC = () => {
  const { items } = useAtomValue(notebookOutline);
  const { activeHeaderId, activeOccurrences } = useActiveOutline(
    findOutlineElements(items),
  );
  const [isHovered, setIsHovered] = React.useState(false);
  const [isFocused, setIsFocused] = React.useState(false);
  const isVisible = isHovered || isFocused;

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
      onFocus={() => setIsFocused(true)}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) {
          setIsFocused(false);
        }
      }}
      className={cn(
        "fixed top-[25vh] right-8 z-10000 print:hidden",
        // Hide on small screens
        "hidden md:block",
      )}
    >
      <OutlineList
        inert={!isVisible}
        className={cn(
          "-top-4 max-h-[70vh] bg-background rounded-lg shadow-lg absolute overflow-auto transition-all duration-300 w-[300px] border",
          isVisible ? "left-[-280px] opacity-100" : "left-[300px] opacity-0",
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
          <button
            type="button"
            aria-label={item.name}
            key={`${identifier}-${idx}`}
            className={cn(
              "h-[2px] bg-muted-foreground/60 focus-visible:outline focus-visible:outline-ring",
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
  inert?: boolean;
  items: OutlineItem[];
  activeHeaderId: string | undefined;
  activeOccurrences: number | undefined;
}> = ({ items, activeHeaderId, activeOccurrences, className, inert }) => {
  // Map of selector to its occurrences
  const seen = new Map<string, number>();
  return (
    <div
      inert={inert}
      className={cn("flex flex-col overflow-auto py-4 pl-2", className)}
    >
      {items.map((item, idx) => {
        const identifier = "id" in item.by ? item.by.id : item.by.path;
        // Keep track of how many times we've seen this selector
        const occurrences = seen.get(identifier) ?? 0;
        seen.set(identifier, occurrences + 1);

        const key = `${identifier}-${idx}`;
        const sharedProps = {
          role: "link",
          tabIndex: 0,
          className: cn(
            "px-2 py-1 cursor-pointer hover:bg-accent/50 hover:text-accent-foreground rounded-l focus-visible:outline focus-visible:outline-ring",
            item.level === 1 && "font-semibold",
            item.level === 2 && "ml-3",
            item.level === 3 && "ml-6",
            item.level === 4 && "ml-9",
            occurrences === activeOccurrences &&
              activeHeaderId === identifier &&
              "text-accent-foreground",
          ),
          onClick: () => scrollToOutlineItem(item, occurrences),
          onKeyDown: (e: React.KeyboardEvent) => {
            if (e.target === e.currentTarget && e.key === "Enter") {
              e.preventDefault();
              scrollToOutlineItem(item, occurrences);
            }
          },
        };

        if (item.html) {
          return (
            <div
              key={key}
              {...sharedProps}
              dangerouslySetInnerHTML={{ __html: item.html }}
            />
          );
        }

        return (
          <div key={key} {...sharedProps}>
            {item.name}
          </div>
        );
      })}
    </div>
  );
};
