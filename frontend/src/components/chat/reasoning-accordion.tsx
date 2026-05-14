/* Copyright 2026 Marimo. All rights reserved. */

import { BotMessageSquareIcon } from "lucide-react";
import React from "react";
import { MarkdownRenderer } from "@/components/markdown/markdown-renderer";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

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
  const [openItem, setOpenItem] = React.useState<string>("");

  // Some reasoning models emit a reasoning part with no surfaced content
  // (e.g. OpenAI's o-series, which hides chain-of-thought but still marks
  // its boundaries on the wire). pydantic-ai's Vercel adapter forwards the
  // empty start/end pair, producing a 0-char ReasoningUIPart. Skip it.
  if (!reasoning && !isStreaming) {
    return null;
  }

  return (
    <Accordion
      key={index}
      type="single"
      collapsible={true}
      className="w-full mb-2"
      value={isStreaming ? "reasoning" : openItem}
      onValueChange={setOpenItem}
    >
      <AccordionItem value="reasoning" className="border-0">
        <AccordionTrigger className="text-xs text-muted-foreground hover:bg-muted/50 px-2 py-1 h-auto rounded-sm [&[data-state=open]>svg]:rotate-180">
          <span className="flex items-center gap-2">
            <BotMessageSquareIcon className="h-3 w-3" />
            {isStreaming ? "Thinking" : "View reasoning"}
            {reasoning.length > 0 && ` (${reasoning.length} chars)`}
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
