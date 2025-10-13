/* Copyright 2024 Marimo. All rights reserved. */

import { AnsiUp } from "ansi_up";
import { ChevronRightIcon, WrapTextIcon } from "lucide-react";
import React, { useLayoutEffect } from "react";
import { ToggleButton } from "react-aria-components";
import { DebuggerControls } from "@/components/debugger/debugger-code";
import { CopyClipboardIcon } from "@/components/icons/copy-icon";
import { prettyPrintHotkey } from "@/components/shortcuts/renderShortcut";
import { Input } from "@/components/ui/input";
import { Tooltip } from "@/components/ui/tooltip";
import type { CellId } from "@/core/cells/ids";
import { isInternalCellName } from "@/core/cells/names";
import type { WithResponse } from "@/core/cells/types";
import type { OutputMessage } from "@/core/kernel/messages";
import { useSelectAllContent } from "@/hooks/useSelectAllContent";
import { cn } from "@/utils/cn";
import { ansiToPlainText, parseHtmlContent } from "@/utils/dom";
import { invariant } from "@/utils/invariant";
import { Strings } from "@/utils/strings";
import { NameCellContentEditable } from "../actions/name-cell-input";
import { ErrorBoundary } from "../boundary/ErrorBoundary";
import { OutputRenderer } from "../Output";
import { useWrapText } from "./useWrapText";

const ansiUp = new AnsiUp();

interface Props {
  cellId: CellId;
  cellName: string;
  className?: string;
  consoleOutputs: WithResponse<OutputMessage>[];
  stale: boolean;
  debuggerActive: boolean;
  onRefactorWithAI?: (opts: { prompt: string }) => void;
  onClear?: () => void;
  onSubmitDebugger: (text: string, index: number) => void;
}

export const ConsoleOutput = (props: Props) => {
  return (
    <ErrorBoundary>
      <ConsoleOutputInternal {...props} />
    </ErrorBoundary>
  );
};

const ConsoleOutputInternal = (props: Props): React.ReactNode => {
  const ref = React.useRef<HTMLDivElement>(null);
  const { wrapText, setWrapText } = useWrapText();
  const {
    consoleOutputs,
    stale,
    cellName,
    cellId,
    onSubmitDebugger,
    onClear,
    onRefactorWithAI,
    className,
  } = props;

  /* The debugger UI needs some work. For now just use the regular
  /* console output. */
  /* if (debuggerActive) {
    return (
      <Debugger
        code={consoleOutputs.map((output) => output.data).join("\n")}
        onSubmit={(text) => onSubmitDebugger(text, consoleOutputs.length - 1)}
      />
    );
  } */

  const hasOutputs = consoleOutputs.length > 0;

  // Enable Ctrl/Cmd-A to select all content within the console output
  const selectAllProps = useSelectAllContent(hasOutputs);

  // Keep scroll at the bottom if it is within 120px of the bottom,
  // so when we add new content, it will lock to the bottom
  //
  // We use flex flex-col-reverse to handle this, but it doesn't
  // always work perfectly when moved form the bottom and back.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) {
      return;
    }
    // N.B. This won't handle large jumps in the scroll position
    // if there is a lot of content added at once.
    // This is 'good enough' for now.
    const threshold = 120;

    const scrollOffset = el.scrollHeight - el.clientHeight;
    const distanceFromBottom = scrollOffset - el.scrollTop;
    if (distanceFromBottom < threshold) {
      el.scrollTop = scrollOffset;
    }
  });

  if (!hasOutputs && isInternalCellName(cellName)) {
    return null;
  }

  const reversedOutputs = [...consoleOutputs].reverse();
  const isPdb = reversedOutputs.some(
    (output) =>
      typeof output.data === "string" && output.data.includes("(Pdb)"),
  );

  // Find the index of the last stdin output since we only want to show
  // the pdb prompt once
  const lastStdInputIdx = reversedOutputs.findIndex(
    (output) => output.channel === "stdin",
  );

  const getOutputString = (event: React.MouseEvent): string => {
    const text = reversedOutputs
      .filter((output) => output.channel !== "pdb")
      .map((output) => {
        // If alt key is pressed, don't parse as HTML
        // If starts with `<`, then assume it's HTML
        if (
          !event.altKey &&
          typeof output.data === "string" &&
          output.data.startsWith("<")
        ) {
          return parseHtmlContent(output.data);
        }

        // Otherwise, convert the ANSI to HTML, then parse as HTML
        return ansiToPlainText(Strings.asString(output.data));
      })
      .join("\n");
    return text;
  };

  const prettyPrintAlt = prettyPrintHotkey("Alt")[1];

  return (
    <div className="relative group">
      {hasOutputs && (
        <div className="absolute top-1 right-5 z-10 opacity-0 group-hover:opacity-100 flex gap-1">
          <CopyClipboardIcon
            tooltip={
              <div className="flex flex-col gap-1">
                <p>Copy console output</p>
                <p className="text-xs text-muted-foreground border-t border-border/50 pt-1">
                  Hold {prettyPrintAlt} for raw output
                </p>
              </div>
            }
            value={getOutputString}
            ariaLabel="Copy console output (Alt for raw)"
            className="h-4 w-4"
          />
          <Tooltip content={wrapText ? "Disable wrap text" : "Wrap text"}>
            <span>
              <ToggleButton
                aria-label="Toggle text wrapping"
                className="p-1 rounded bg-transparent text-muted-foreground data-hovered:text-foreground data-selected:text-foreground"
                isSelected={wrapText}
                onChange={setWrapText}
              >
                <WrapTextIcon className="h-4 w-4" />
              </ToggleButton>
            </span>
          </Tooltip>
        </div>
      )}
      <div
        title={stale ? "This console output is stale" : undefined}
        data-testid="console-output-area"
        ref={ref}
        {...selectAllProps}
        // biome-ignore lint/a11y/noNoninteractiveTabindex: Needed to capture keypress events
        tabIndex={0}
        className={cn(
          "console-output-area overflow-hidden rounded-b-lg flex flex-col-reverse w-full gap-1 focus:outline-hidden",
          stale && "marimo-output-stale",
          hasOutputs ? "p-5" : "p-3",
          className,
        )}
      >
        {reversedOutputs.map((output, idx) => {
          if (output.channel === "pdb") {
            return null;
          }

          if (output.channel === "stdin") {
            invariant(
              typeof output.data === "string",
              "Expected data to be a string",
            );

            const originalIdx = consoleOutputs.length - idx - 1;

            if (output.response == null && lastStdInputIdx === idx) {
              return (
                <StdInput
                  key={idx}
                  output={output.data}
                  isPdb={isPdb}
                  onSubmit={(text) => onSubmitDebugger(text, originalIdx)}
                  onClear={onClear}
                />
              );
            }

            return (
              <StdInputWithResponse
                key={idx}
                output={output.data}
                response={output.response}
              />
            );
          }

          return (
            <React.Fragment key={idx}>
              <OutputRenderer
                cellId={cellId}
                onRefactorWithAI={onRefactorWithAI}
                message={output}
                wrapText={wrapText}
              />
            </React.Fragment>
          );
        })}
        <NameCellContentEditable
          value={cellName}
          cellId={cellId}
          className="bg-(--slate-4) border-(--slate-4) hover:bg-(--slate-5) dark:border-(--sky-5) dark:bg-(--sky-6) dark:text-(--sky-12) text-(--slate-12) rounded-l rounded-br-lg absolute right-0 bottom-0 text-xs px-1.5 py-0.5 font-mono max-w-[75%] whitespace-nowrap overflow-hidden"
        />
      </div>
    </div>
  );
};

const StdInput = (props: {
  onSubmit: (text: string) => void;
  onClear?: () => void;
  output: string;
  response?: string;
  isPdb: boolean;
}) => {
  return (
    <div className="flex gap-2 items-center pt-2">
      {renderText(props.output)}
      <Input
        data-testid="console-input"
        // This is used in <StdinBlockingAlert> to find the input
        data-stdin-blocking={true}
        type="text"
        autoComplete="off"
        autoFocus={true}
        icon={<ChevronRightIcon className="w-5 h-5" />}
        className="m-0 h-8 focus-visible:shadow-xs-solid"
        placeholder="stdin"
        // Capture the keydown event to prevent default behavior
        onKeyDownCapture={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            props.onSubmit(e.currentTarget.value);
            e.preventDefault();
            e.stopPropagation();
          }

          // Prevent running the cell
          if (e.key === "Enter" && e.metaKey) {
            e.preventDefault();
            e.stopPropagation();
          }
        }}
      />
      {props.isPdb && (
        <DebuggerControls onSubmit={props.onSubmit} onClear={props.onClear} />
      )}
    </div>
  );
};

const StdInputWithResponse = (props: { output: string; response?: string }) => {
  return (
    <div className="flex gap-2 items-center">
      {renderText(props.output)}
      <span className="text-(--sky-11)">{props.response}</span>
    </div>
  );
};

const renderText = (text: string | null) => {
  if (!text) {
    return null;
  }

  return (
    <span dangerouslySetInnerHTML={{ __html: ansiUp.ansi_to_html(text) }} />
  );
};
