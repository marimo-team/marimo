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
  CopyIcon,
  BugPlayIcon,
} from "lucide-react";
import { useState } from "react";
import { useAtomValue } from "jotai";
import { aiEnabledAtom } from "@/core/config/config";
import type { DOMNode } from "html-react-parser";

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
  extractAllTracebackInfo,
  getTracebackInfo,
} from "@/utils/traceback";
import type { CellId } from "@/core/cells/ids";
import { Tooltip } from "@/components/ui/tooltip";
import { Kbd } from "@/components/ui/kbd";
import { insertDebuggerAtLine } from "@/core/codemirror/editing/debugging";
import { getCellEditorView } from "@/core/cells/cells";

interface Props {
  cellId: CellId | undefined;
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
  cellId,
}: Props): JSX.Element => {
  const htmlTraceback = renderHTML({
    html: traceback,
    additionalReplacements: [replaceTracebackFilenames, replaceTracebackPrefix],
  });
  const [expanded, setExpanded] = useState(true);

  const lastTracebackLine = lastLine(traceback);
  const aiEnabled = useAtomValue(aiEnabledAtom);

  // Get last traceback info
  const lastTracebackInfo = extractAllTracebackInfo(traceback)?.at(-1);

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
          <AccordionContent className="text-muted-foreground px-4 pt-2 text-xs overflow-auto">
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
        {lastTracebackInfo && (
          <Button
            size="xs"
            variant="outline"
            onClick={() => {
              const view = getCellEditorView(lastTracebackInfo.cellId);
              if (view) {
                insertDebuggerAtLine(view, lastTracebackInfo.lineNumber);
              }
            }}
          >
            <BugPlayIcon className="h-3 w-3 mr-2" />
            Insert breakpoint
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
    const tooltipContent = <InsertBreakpointContent />;
    return (
      <span className="nb">
        <span className="inline-flex items-center">
          <CellLinkTraceback
            cellId={info.cellId}
            lineNumber={info.lineNumber}
          />
          <Tooltip content={tooltipContent}>
            <button
              type="button"
              className="ml-1 p-1 rounded-sm hover:bg-muted transition-all inline"
            >
              <BugPlayIcon
                onClick={() => {
                  const view = getCellEditorView(info.cellId);
                  if (view) {
                    insertDebuggerAtLine(view, info.lineNumber);
                  }
                }}
                className="h-3 w-3"
              />
            </button>
          </Tooltip>
        </span>
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

const InsertBreakpointContent = () => {
  return (
    <>
      Insert a <Kbd className="inline">breakpoint()</Kbd> at this line
    </>
  );
};
