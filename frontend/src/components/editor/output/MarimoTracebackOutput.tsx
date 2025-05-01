/* Copyright 2024 Marimo. All rights reserved. */

import { cn } from "../../../utils/cn";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
} from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { renderHTML } from "@/plugins/core/RenderHTML";

import {
  BugIcon,
  ChevronDown,
  ExternalLinkIcon,
  SearchIcon,
  MessageCircleIcon,
  HelpCircleIcon,
  CopyIcon,
} from "lucide-react";
import { useState } from "react";
import { useAtomValue } from "jotai";
import { aiEnabledAtom } from "@/core/config/config";
import { Element, Text, type DOMNode } from "html-react-parser";

import { CellLinkTraceback } from "../links/cell-link";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { copyToClipboard } from "@/utils/copy";
import {
  elementContainsMarimoCellFile,
  getTracebackInfo,
} from "@/utils/traceback";

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
  const htmlTraceback = renderHTML({
    html: traceback,
    additionalReplacements: [replaceTracebackFilenames, replaceTracebackPrefix],
  });
  const [expanded, setExpanded] = useState(true);

  const lastTracebackLine = lastLine(traceback);
  const aiEnabled = useAtomValue(aiEnabledAtom);

  const handleRefactorWithAI = () => {
    onRefactorWithAI?.({
      prompt: `My code gives the following error:\n\n${lastTracebackLine}`,
    });
  };

  const [error, errorMessage] = lastTracebackLine.split(":", 2);

  return (
    <div className="flex flex-col gap-2 min-w-full w-fit">
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
            <div className="text-sm inline font-mono">
              <span className="text-destructive">{error || "Error"}:</span>{" "}
              {errorMessage}
            </div>
          </div>
          <AccordionContent className="px-4 text-muted-foreground px-4 pt-2 text-xs overflow-auto">
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
        <DropdownMenu>
          <DropdownMenuTrigger asChild={true}>
            <Button size="xs" variant="text">
              Get help
              <ChevronDown className="h-3 w-3 ml-1" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuItem asChild={true}>
              <a
                target="_blank"
                href={`https://www.google.com/search?q=${encodeURIComponent(lastTracebackLine)}`}
                rel="noreferrer"
              >
                <SearchIcon className="h-4 w-4 mr-2" />
                Search on Google
                <ExternalLinkIcon className="h-3 w-3 ml-auto" />
              </a>
            </DropdownMenuItem>
            <DropdownMenuItem asChild={true}>
              <a target="_blank" href="https://marimo.io/discord?ref=notebook">
                <MessageCircleIcon className="h-4 w-4 mr-2" />
                Ask in Discord
                <ExternalLinkIcon className="h-3 w-3 ml-auto" />
              </a>
            </DropdownMenuItem>
            <DropdownMenuItem asChild={true}>
              <a
                target="_blank"
                href={`https://community.marimo.io/search?q=${encodeURIComponent(lastTracebackLine)}`}
              >
                <HelpCircleIcon className="h-4 w-4 mr-2" />
                Search Community Forum
                <ExternalLinkIcon className="h-3 w-3 ml-auto" />
              </a>
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => {
                // Strip HTML from the traceback
                const div = document.createElement("div");
                div.innerHTML = traceback;
                const textContent = div.textContent || "";
                copyToClipboard(textContent);
              }}
            >
              <CopyIcon className="h-4 w-4 mr-2" />
              Copy to clipboard
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
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

export const replaceTracebackFilenames = (domNode: DOMNode) => {
  const info = getTracebackInfo(domNode);
  if (info) {
    return (
      <span className="nb">
        <CellLinkTraceback cellId={info.cellId} lineNumber={info.lineNumber} />
      </span>
    );
  }
};

export const replaceTracebackPrefix = (domNode: DOMNode) => {
  if (
    domNode instanceof Text &&
    domNode.nodeValue?.includes("File") &&
    domNode.next instanceof Element &&
    elementContainsMarimoCellFile(domNode.next)
  ) {
    return <>{domNode.nodeValue.replace("File", "Cell")}</>;
  }
};
