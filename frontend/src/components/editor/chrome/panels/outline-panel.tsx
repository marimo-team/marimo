/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { notebookOutline } from "../../../../core/cells/cells";
import { useAtomValue } from "jotai";
import { cn } from "@/utils/cn";
import { ScrollTextIcon } from "lucide-react";
import { PanelEmptyState } from "./empty-state";

import "./outline-panel.css";

export const OutlinePanel: React.FC = () => {
  const outline = useAtomValue(notebookOutline);

  if (outline.items.length === 0) {
    return (
      <PanelEmptyState
        title="No outline"
        description="Add markdown headings to your notebook to create an outline."
        icon={<ScrollTextIcon />}
      />
    );
  }

  const handleGoToItem = (id: string, index: number) => {
    // Selectors may be duplicated, so we need to use querySelectorAll
    // IDs that start with a number are invalid, so we need to escape them
    const elems = document.querySelectorAll(`[id="${CSS.escape(id)}"]`);
    const el = elems[index];
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });

      // Add underline to the element for a few seconds
      el.classList.add("outline-item-highlight");
      setTimeout(() => {
        el.classList.remove("outline-item-highlight");
      }, 3000);
    }
  };

  // Map of selector to its occurrences
  const seen = new Map<string, number>();
  return (
    <div className="flex flex-col overflow-auto py-4 pl-2">
      {outline.items.map((item) => {
        // Keep track of how many times we've seen this selector
        const occurrences = seen.get(item.id) ?? 0;
        seen.set(item.id, occurrences + 1);

        return (
          <div
            key={item.id}
            className={cn(
              "px-2 py-1 cursor-pointer hover:bg-accent/50 hover:text-accent-foreground rounded-l",
              item.level === 1 && "font-semibold",
              item.level === 2 && "ml-3",
              item.level === 3 && "ml-6",
              item.level === 4 && "ml-9",
            )}
            onClick={() => handleGoToItem(item.id, occurrences)}
          >
            {item.name}
          </div>
        );
      })}
    </div>
  );
};
