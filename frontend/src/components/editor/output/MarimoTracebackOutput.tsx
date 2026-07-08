/* Copyright 2026 Marimo. All rights reserved. */

import { type DOMNode, Element, Text } from "html-react-parser";
import { useAtomValue } from "jotai";
import {
  BugPlayIcon,
  ChevronDown,
  ChevronRight,
  CopyIcon,
  ExternalLinkIcon,
  MessageCircleIcon,
  SearchIcon,
} from "lucide-react";
import { type JSX, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Kbd } from "@/components/ui/kbd";
import { Tooltip } from "@/components/ui/tooltip";
import { getCellEditorView } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { SCRATCH_CELL_ID } from "@/core/cells/ids";
import { insertDebuggerAtLine } from "@/core/codemirror/editing/debugging";
import { aiFeaturesEnabledAtom } from "@/core/config/config";
import { getRequestClient } from "@/core/network/requests";
import { isStaticNotebook } from "@/core/static/static-state";
import { isWasm } from "@/core/wasm/utils";
import { renderHTML } from "@/plugins/core/RenderHTML";
import { sanitizeHtml } from "@/plugins/core/sanitize-html";
import { copyToClipboard } from "@/utils/copy";
import {
  containsMangledLocal,
  splitMangledLocals,
} from "@/utils/local-variables";
import {
  elementContainsMarimoCellFile,
  extractAllTracebackInfo,
  getTracebackInfo,
} from "@/utils/traceback";
import { useOpenAiAssistant } from "../chrome/wrapper/useOpenAiAssistant";
import { AIFixButton, buildFixInChatPrompt } from "../errors/auto-fix";
import { MangledSegments } from "../errors/mangled-local-chip";
import { CellLinkTraceback } from "../links/cell-link";
import type { OnRefactorWithAI } from "../Output";

interface Props {
  cellId: CellId | undefined;
  traceback: string;
  onRefactorWithAI?: OnRefactorWithAI;
}

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
    additionalReplacements: [
      replaceTracebackFilenames,
      replaceTracebackPrefix,
      replaceMangledLocal,
    ],
  });

  const lastTracebackLine = lastLine(traceback);
  const aiFeaturesEnabled = useAtomValue(aiFeaturesEnabledAtom);
  const openAiAssistant = useOpenAiAssistant();

  // Get last traceback info
  const tracebackInfo = extractAllTracebackInfo(traceback)?.at(0);

  // Don't show in wasm, static notebooks, or scratchpad
  const showDebugger =
    tracebackInfo &&
    tracebackInfo.kind === "cell" &&
    !isWasm() &&
    !isStaticNotebook() &&
    cellId !== SCRATCH_CELL_ID;

  const showAIFix =
    onRefactorWithAI && aiFeaturesEnabled && !isStaticNotebook();

  const showSearch = !isStaticNotebook();

  const [isOpen, setIsOpen] = useState(true);

  const handleRefactorWithAI = (triggerImmediately: boolean) => {
    onRefactorWithAI?.({
      prompt: `My code gives the following error:\n\n${lastTracebackLine}`,
      triggerImmediately,
    });
  };

  const openAISidebar = () => {
    openAiAssistant({
      prompt: buildFixInChatPrompt(cellId, lastTracebackLine),
    });
  };

  return (
    <div className="flex flex-col gap-2 min-w-full w-fit">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        aria-label={isOpen ? "Collapse traceback" : "Expand traceback"}
        className="self-start flex items-center gap-1 pt-2 text-muted-foreground/70 hover:text-muted-foreground transition-colors"
      >
        {isOpen ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
        <span className="text-[0.6875rem] uppercase tracking-wider">
          Traceback
        </span>
      </button>
      {isOpen && (
        <div className="text-muted-foreground pr-4 text-xs overflow-auto">
          {htmlTraceback}
        </div>
      )}
      <div className="flex gap-2">
        {showAIFix && (
          <AIFixButton
            tooltip="Fix with AI"
            openPrompt={() => handleRefactorWithAI(false)}
            applyAutofix={() => handleRefactorWithAI(true)}
            openChat={openAISidebar}
          />
        )}
        {showDebugger && (
          <Tooltip content={"Attach pdb to the exception point."}>
            <Button
              size="xs"
              variant="outline"
              onClick={() => {
                getRequestClient().sendPdb({ cellId: tracebackInfo.cellId });
              }}
            >
              <BugPlayIcon className="h-3 w-3 mr-2" />
              Launch debugger
            </Button>
          </Tooltip>
        )}
        {showSearch && (
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
                <a
                  target="_blank"
                  href="https://marimo.io/discord?ref=notebook"
                  rel="noopener"
                >
                  <MessageCircleIcon className="h-4 w-4 mr-2" />
                  Ask in Discord
                  <ExternalLinkIcon className="h-3 w-3 ml-auto" />
                </a>
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => {
                  // Strip HTML from the traceback (sanitize first to prevent XSS)
                  const div = document.createElement("div");
                  div.innerHTML = sanitizeHtml(traceback);
                  const textContent = div.textContent || "";
                  copyToClipboard(textContent);
                }}
              >
                <CopyIcon className="h-4 w-4 mr-2" />
                Copy to clipboard
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
    </div>
  );
};

function lastLine(text: string): string {
  const el = document.createElement("div");
  el.innerHTML = sanitizeHtml(text);
  const lines = el.textContent?.split("\n").filter(Boolean);
  return lines?.at(-1) || "";
}

export const replaceTracebackFilenames = (domNode: DOMNode) => {
  const info = getTracebackInfo(domNode);
  if (info?.kind === "cell") {
    const tooltipContent = <InsertBreakpointContent />;
    return (
      <span className="nb">
        <span className="inline-flex items-center">
          <CellLinkTraceback
            cellId={info.cellId}
            lineNumber={info.lineNumber}
          />
          {!isWasm() && (
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
          )}
        </span>
      </span>
    );
  }
  if (info?.kind === "file") {
    return (
      <div
        className="inline-block cursor-pointer text-destructive hover:underline"
        onClick={(_) => {
          getRequestClient().openFile({
            path: info.filePath,
            lineNumber: info.lineNumber,
          });
        }}
      >
        <span className="nb">"{info.filePath}"</span>
      </div>
    );
  }
};

/**
 * Replace any cell-local mangled name (`_cell_<id>_<name>`) inside a text
 * node with a {@link MangledLocalChip}. The mangled name appears in both
 * the final `NameError:` line and inside compiled-cell source lines because
 * the compiler rewrites underscore-prefixed references at AST-visit time.
 */
export const replaceMangledLocal = (domNode: DOMNode) => {
  if (!(domNode instanceof Text) || !domNode.nodeValue) {
    return;
  }
  if (!containsMangledLocal(domNode.nodeValue)) {
    return;
  }
  const segments = splitMangledLocals(domNode.nodeValue);
  return <MangledSegments segments={segments} />;
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
