/* Copyright 2024 Marimo. All rights reserved. */

import { cn } from "../../../utils/cn";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
} from "@/components/ui/accordion";
import { Button, buttonVariants } from "@/components/ui/button";
import { renderHTML } from "@/plugins/core/RenderHTML";

import "./traceback-output.css";
import { BugIcon, ChevronDown, ExternalLinkIcon } from "lucide-react";
import { useState } from "react";
import { useAtomValue } from "jotai";
import { aiEnabledAtom } from "@/core/config/config";

interface Props {
  traceback: string;
  onRefactorWithAI?: (opts: { prompt: string }) => void;
}

const KEY = "item";

/**
 * List of errors due to violations of Marimo semantics.
 */
export const MarimoTracebackOutput = ({
  onRefactorWithAI,
  traceback,
}: Props): JSX.Element => {
  const htmlTraceback = renderHTML({ html: traceback });
  const [expanded, setExpanded] = useState(true);

  const lastTracebackLine = lastLine(traceback);
  const aiEnabled = useAtomValue(aiEnabledAtom);

  const handleRefactorWithAI = () => {
    onRefactorWithAI?.({
      prompt: `My code gives the following error: ${lastTracebackLine}`,
    });
  };

  return (
    <div className="flex flex-col gap-2">
      <Accordion type="single" collapsible={true} value={expanded ? KEY : ""}>
        <AccordionItem value={KEY} className="border-none">
          <div
            className="flex gap-2 h-10 px-2 hover:bg-muted rounded-sm select-none items-center cursor-pointer transition-all"
            onClick={() => setExpanded((prev) => !prev)}
          >
            <ChevronDown
              className={cn(
                "h-4 w-4 text-muted-foreground transition-transform duration-200 flex-shrink-0",
                expanded ? "rotate-180" : "rotate-0",
              )}
            />
            <div className="pb-5">
              <div className="traceback-header text-destructive line-clamp-1 text-sm inline">
                {htmlTraceback}
              </div>
            </div>
          </div>
          <AccordionContent className="px-4 text-muted-foreground px-4 pt-2 text-xs">
            {htmlTraceback}
          </AccordionContent>
        </AccordionItem>
      </Accordion>
      <div className="flex gap-2">
        {onRefactorWithAI && aiEnabled && (
          <Button size="xs" variant="outline" onClick={handleRefactorWithAI}>
            <BugIcon className="h-3 w-3 mr-2" />
            Fix with AI
          </Button>
        )}
        <a
          className={buttonVariants({ size: "xs", variant: "text" })}
          target="_blank"
          href={`https://www.google.com/search?q=${encodeURIComponent(lastTracebackLine)}`}
          rel="noreferrer"
        >
          Search on Google
          <ExternalLinkIcon className="h-3 w-3 ml-1" />
        </a>
      </div>
    </div>
  );
};

function lastLine(text: string): string {
  const el = document.createElement("div");
  el.innerHTML = text;
  const lines = el.textContent?.split("\n").filter(Boolean);
  return lines?.at(-1) || "";
}
