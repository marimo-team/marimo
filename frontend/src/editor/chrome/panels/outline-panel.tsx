/* Copyright 2023 Marimo. All rights reserved. */
import React from "react";
import { notebookOutline } from "../../../core/state/cells";
import { useAtomValue } from "jotai";
import { cn } from "@/lib/utils";
import { ScrollTextIcon } from "lucide-react";

import "./outline-panel.css";

export const OutlinePanel: React.FC = () => {
  const outline = useAtomValue(notebookOutline);

  if (outline.items.length === 0) {
    return (
      <div className="mx-6 my-6 flex flex-row gap-2 items-center rounded-lg">
        <ScrollTextIcon className="text-muted-foreground" />
        <span className="mt-[0.25rem] text-muted-foreground">No outline</span>
      </div>
    );
  }

  const handleGoToItem = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });

      // Add underline to the element for a few seconds
      el.classList.add("outline-item-highlight");
      setTimeout(() => {
        el.classList.remove("outline-item-highlight");
      }, 3000);
    }
  };

  return (
    <div className="flex flex-col overflow-auto py-4 pl-2">
      {outline.items.map((item) => (
        <div
          key={item.id}
          className={cn(
            "px-2 py-1 cursor-pointer hover:bg-accent/50 hover:text-accent-foreground rounded-l",
            item.level === 1 && "font-semibold",
            item.level === 2 && "ml-3",
            item.level === 3 && "ml-6",
            item.level === 4 && "ml-9"
          )}
          onClick={() => handleGoToItem(item.id)}
        >
          {item.name}
        </div>
      ))}
    </div>
  );
};
