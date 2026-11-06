/* Copyright 2026 Marimo. All rights reserved. */

import type { PropsWithChildren } from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { formatToolName, type ToolState } from "./shared";

interface ToolActivity {
  toolName: string;
  state: ToolState;
}

export function ToolActivityGroup({
  tools,
  isActive,
  children,
}: PropsWithChildren<{ tools: ToolActivity[]; isActive: boolean }>) {
  const pending = tools.some((tool) => tool.state !== "output-available");
  const editing = tools.every(
    (tool) => formatToolName(tool.toolName) === "edit_notebook_tool",
  );
  const count = tools.length;
  const label = pending
    ? isActive
      ? editing
        ? "Editing notebook…"
        : "Working…"
      : "Stopped before completing all steps"
    : editing
      ? `Edited notebook · ${count} ${count === 1 ? "operation" : "operations"}`
      : `Completed ${count} ${count === 1 ? "step" : "steps"}`;

  return (
    <Accordion type="single" collapsible={true} className="my-1 w-full">
      <AccordionItem value="activity" className="border-0">
        <AccordionTrigger className="h-auto pl-0 pr-2 py-1 gap-2 rounded text-xs font-normal text-muted-foreground hover:bg-(--slate-2) hover:text-foreground hover:no-underline">
          {label}
        </AccordionTrigger>
        <AccordionContent className="pb-2 pl-3 border-l border-border">
          {children}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}
