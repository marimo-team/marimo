/* Copyright 2024 Marimo. All rights reserved. */

import {
  CheckCircleIcon,
  Loader2,
  WrenchIcon,
  XCircleIcon,
} from "lucide-react";
import React from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { cn } from "@/utils/cn";

interface ToolCallAccordionProps {
  toolName: string;
  result?: string | null;
  error?: string;
  index?: number;
  state?: "partial-call" | "call" | "result";
}

export const ToolCallAccordion: React.FC<ToolCallAccordionProps> = ({
  toolName,
  result,
  error,
  index = 0,
  state,
}) => {
  const hasResult = state === "result" && (result || error);
  const status = error ? "error" : hasResult ? "success" : "loading";

  const getStatusIcon = () => {
    switch (status) {
      case "loading":
        return <Loader2 className="h-3 w-3 animate-spin" />;
      case "error":
        return <XCircleIcon className="h-3 w-3 text-destructive" />;
      case "success":
        return <CheckCircleIcon className="h-3 w-3 text-green-600" />;
      default:
        return <WrenchIcon className="h-3 w-3" />;
    }
  };

  const getStatusText = () => {
    if (status === "loading") {
      return "Running: ";
    }
    if (error) {
      return "Failed: ";
    }
    if (hasResult) {
      return "Done: ";
    }
    return "Tool call";
  };

  return (
    <Accordion
      key={`tool-${index}`}
      type="single"
      collapsible={true}
      className="w-full my-4"
    >
      <AccordionItem value="tool-call" className="border-0">
        <AccordionTrigger
          className={cn(
            "h-6 text-xs border-border !shadow-none !ring-0 bg-muted hover:bg-muted/30 py-0 px-2 gap-1 rounded-sm [&[data-state=open]>svg]:rotate-180",
            status === "error" && "text-destructive/80",
            status === "success" && "text-green-600/80",
          )}
        >
          <span className="flex items-center gap-1">
            {getStatusIcon()}
            {getStatusText()}:{" "}
            <code className="font-mono text-xs">{toolName}</code>
          </span>
        </AccordionTrigger>
        <AccordionContent className="pb-2 px-2">
          {/* Only show content when tool is complete */}
          {hasResult && (
            <div className="space-y-3">
              {/* Result */}
              {result && (
                <div>
                  <div className="text-xs font-medium text-muted-foreground mt-2 mb-1">
                    Result:
                  </div>
                  <div className="text-xs font-medium text-muted-foreground mb-1">
                    {typeof result === "string"
                      ? result
                      : JSON.stringify(result, null, 2)}
                  </div>
                </div>
              )}

              {/* Error */}
              {error && (
                <div>
                  <div className="text-xs font-medium text-destructive mb-1">
                    Error:
                  </div>
                  <div className="bg-destructive/10 border border-destructive/20 rounded-md p-3 text-sm text-destructive">
                    {error}
                  </div>
                </div>
              )}
            </div>
          )}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
};
