/* Copyright 2026 Marimo. All rights reserved. */

import { CheckCircleIcon, Loader2, XCircleIcon } from "lucide-react";
import React from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { cn } from "@/utils/cn";

interface SimpleAccordionProps {
  title: string | React.ReactNode;
  children: React.ReactNode | string;
  status?: "loading" | "error" | "success";
  index?: number;
  defaultIcon?: React.ReactNode;
}

export const SimpleAccordion: React.FC<SimpleAccordionProps> = ({
  title,
  children,
  status,
  index = 0,
  defaultIcon,
}) => {
  const getStatusIcon = () => {
    switch (status) {
      case "loading":
        return <Loader2 className="h-3 w-3 animate-spin" />;
      case "error":
        return <XCircleIcon className="h-3 w-3 text-destructive" />;
      case "success":
        return <CheckCircleIcon className="h-3 w-3 text-[var(--blue-9)]" />;
      default:
        return defaultIcon;
    }
  };

  return (
    <Accordion
      key={`tool-${index}`}
      type="single"
      collapsible={true}
      className="w-full"
    >
      <AccordionItem value="tool-call" className="border-0">
        <AccordionTrigger
          className={cn(
            "py-1 text-xs border-border shadow-none! ring-0! bg-muted hover:bg-muted/30 px-2 gap-1 rounded-sm [&[data-state=open]>svg]:rotate-180",
            status === "error" && "text-destructive/80",
            status === "success" && "text-[var(--blue-8)]",
          )}
        >
          <span className="flex items-center gap-1">
            {getStatusIcon()}
            <code className="font-mono text-xs truncate">{title}</code>
          </span>
        </AccordionTrigger>
        <AccordionContent className="p-2">
          <div className="space-y-3 max-h-64 overflow-y-auto scrollbar-thin">
            {status !== "error" && (
              <div className="text-xs font-medium text-muted-foreground mb-1">
                {children}
              </div>
            )}

            {status === "error" && (
              <div className="bg-destructive/10 border border-destructive/20 rounded-md p-3 text-xs text-destructive">
                {children}
              </div>
            )}
          </div>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
};
