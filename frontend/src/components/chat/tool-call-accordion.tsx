/* Copyright 2024 Marimo. All rights reserved. */

import type { ToolUIPart } from "ai";
import { isEmpty } from "lodash-es";
import {
  CheckCircleIcon,
  InfoIcon,
  Loader2,
  WrenchIcon,
  XCircleIcon,
} from "lucide-react";
import React from "react";
import { z } from "zod";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { cn } from "@/utils/cn";

// Zod schema matching the Python SuccessResult dataclass
const SuccessResultSchema = z
  .object({
    status: z.string().default("success"),
    auth_required: z.boolean().default(false),
    action_url: z.any(),
    next_steps: z.any(),
    meta: z.any(),
    message: z.string().nullish(),
  })
  .passthrough();

type SuccessResult = z.infer<typeof SuccessResultSchema>;

const PrettySuccessResult: React.FC<{ data: SuccessResult }> = ({ data }) => {
  const {
    status,
    auth_required,
    action_url: _action_url,
    meta: _meta,
    next_steps: _next_steps,
    message,
    ...rest
  } = data;

  return (
    <div className="py-1 flex flex-col gap-1">
      {/* Status */}
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-[var(--grass-11)] capitalize">
          {status}
        </span>
        {auth_required && (
          <span className="text-xs px-2 py-0.5 bg-[var(--amber-2)] text-[var(--amber-11)] rounded-full">
            Auth Required
          </span>
        )}
      </div>

      {/* Message */}
      {message && (
        <div className="flex items-start gap-2">
          <InfoIcon className="h-3 w-3 text-[var(--blue-11)] mt-0.5 flex-shrink-0" />
          <div className="text-xs text-foreground">{message}</div>
        </div>
      )}

      {/* Data */}
      {rest && (
        <div className="flex flex-col gap-1">
          {Object.entries(rest).map(([key, value]) => {
            if (isEmpty(value)) {
              return null;
            }
            return (
              <div key={key}>
                <div className="text-xs font-medium text-muted-foreground mb-1 capitalize">
                  {key}:
                </div>
                <pre className="bg-[var(--slate-2)] p-1 text-muted-foreground border border-[var(--slate-4)] rounded text-xs overflow-auto scrollbar-thin max-h-64">
                  {JSON.stringify(value, null, 2)}
                </pre>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

const ResultRenderer: React.FC<{ result: unknown }> = ({ result }) => {
  // Try to parse the result with our Zod schema
  const parseResult = SuccessResultSchema.safeParse(result);

  if (parseResult.success) {
    // If it matches the SuccessResult schema, show the pretty UI
    return <PrettySuccessResult data={parseResult.data} />;
  }

  // Otherwise, fall back to the current JSON viewer
  return (
    <div className="text-xs font-medium text-muted-foreground mb-1">
      {typeof result === "string" ? result : JSON.stringify(result, null, 2)}
    </div>
  );
};

interface ToolCallAccordionProps {
  toolName: string;
  result: unknown;
  error?: string;
  index?: number;
  state?: ToolUIPart["state"];
  className?: string;
}

export const ToolCallAccordion: React.FC<ToolCallAccordionProps> = ({
  toolName,
  result,
  error,
  index = 0,
  state,
  className,
}) => {
  const hasResult = state === "output-available" && (result || error);
  const status = error ? "error" : hasResult ? "success" : "loading";

  const getStatusIcon = () => {
    switch (status) {
      case "loading":
        return <Loader2 className="h-3 w-3 animate-spin" />;
      case "error":
        return <XCircleIcon className="h-3 w-3 text-[var(--red-11)]" />;
      case "success":
        return <CheckCircleIcon className="h-3 w-3 text-[var(--grass-11)]" />;
      default:
        return <WrenchIcon className="h-3 w-3" />;
    }
  };

  const getStatusText = () => {
    if (status === "loading") {
      return "Running";
    }
    if (error) {
      return "Failed";
    }
    if (hasResult) {
      return "Done";
    }
    return "Tool call";
  };

  return (
    <Accordion
      key={`tool-${index}`}
      type="single"
      collapsible={true}
      className={cn("w-full", className)}
    >
      <AccordionItem value="tool-call" className="border-0">
        <AccordionTrigger
          className={cn(
            "h-6 text-xs border-border shadow-none! ring-0! bg-muted/60 hover:bg-muted py-0 px-2 gap-1 rounded-sm [&[data-state=open]>svg]:rotate-180 hover:no-underline",
            status === "error" && "text-[var(--red-11)]/80",
            status === "success" && "text-[var(--grass-11)]/80",
          )}
        >
          <span className="flex items-center gap-1">
            {getStatusIcon()}
            {getStatusText()}:
            <code className="font-mono text-xs">
              {formatToolName(toolName)}
            </code>
          </span>
        </AccordionTrigger>
        <AccordionContent className="pb-2 px-2">
          {/* Only show content when tool is complete */}
          {hasResult && (
            <div className="space-y-3">
              {result !== undefined && result !== null && (
                <ResultRenderer result={result} />
              )}

              {/* Error */}
              {error && (
                <div>
                  <div className="text-xs font-medium text-[var(--red-11)] mb-1">
                    Error:
                  </div>
                  <div className="bg-[var(--red-2)] border border-[var(--red-6)] rounded-md p-3 text-sm text-[var(--red-11)]">
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

function formatToolName(toolName: string) {
  return toolName.replace("tool-", "");
}
