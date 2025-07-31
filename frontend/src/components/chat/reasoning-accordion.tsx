/* Copyright 2024 Marimo. All rights reserved. */

import { BotMessageSquareIcon } from "lucide-react";
import React from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { MarkdownRenderer } from "./markdown-renderer";

interface ReasoningAccordionProps {
  reasoning: string;
  index?: number;
  isStreaming?: boolean;
}

export const ReasoningAccordion: React.FC<ReasoningAccordionProps> = ({
  reasoning,
  index = 0,
  isStreaming = false,
}) => {
  return (
    <Accordion
      key={index}
      type="single"
      collapsible={true}
      className="w-full mb-2"
      value={isStreaming ? "reasoning" : undefined}
    >
      <AccordionItem value="reasoning" className="border-0">
        <AccordionTrigger className="text-xs text-muted-foreground hover:bg-muted/50 px-2 py-1 h-auto rounded-sm [&[data-state=open]>svg]:rotate-180">
          <span className="flex items-center gap-2">
            <BotMessageSquareIcon className="h-3 w-3" />
            {isStreaming ? "Thinking" : "View reasoning"} ({reasoning.length}{" "}
            chars)
          </span>
        </AccordionTrigger>
        <AccordionContent className="pb-2 px-2">
          <div className="bg-muted/30 border border-muted/50 rounded-md p-3 italic text-muted-foreground/90 relative">
            <div className="pr-6">
              <MarkdownRenderer content={reasoning} />
            </div>
          </div>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
};
