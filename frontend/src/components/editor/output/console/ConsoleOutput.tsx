/* Copyright 2026 Marimo. All rights reserved. */

import {
  ChevronRightIcon,
  ChevronsDownUpIcon,
  ChevronsUpDownIcon,
  WrapTextIcon,
} from "lucide-react";
import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { ToggleButton } from "react-aria-components";
import { DebuggerControls } from "@/components/debugger/debugger-code";
import { CopyClipboardIcon } from "@/components/icons/copy-icon";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tooltip } from "@/components/ui/tooltip";
import type { CellId } from "@/core/cells/ids";
import { isInternalCellName } from "@/core/cells/names";
import { useExpandedConsoleOutput } from "@/core/cells/outputs";
import type { WithResponse } from "@/core/cells/types";
import type { OutputMessage } from "@/core/kernel/messages";
import {
  type UseInputHistoryReturn,
  useInputHistory,
} from "@/hooks/useInputHistory";
import { useOverflowDetection } from "@/hooks/useOverflowDetection";
import { useSelectAllContent } from "@/hooks/useSelectAllContent";
import { cn } from "@/utils/cn";
import { invariant } from "@/utils/invariant";
import { NameCellContentEditable } from "../../actions/name-cell-input";
import { ErrorBoundary } from "../../boundary/ErrorBoundary";
import { type OnRefactorWithAI, OutputRenderer } from "../../Output";
import { useWrapText } from "../useWrapText";
import { processOutput } from "./process-output";
import { RenderTextWithLinks } from "./text-rendering";

/**
 * Delay in ms before clearing console outputs.
 * This prevents flickering when a cell re-runs and outputs are briefly cleared
 * before new outputs arrive (e.g., plt.show() with a slider).
 */
export const CONSOLE_CLEAR_DEBOUNCE_MS = 200;

/**
 * Debounces the clearing of console outputs.
 * - Non-empty updates are applied immediately.
 * - Transitions to empty are delayed by CONSOLE_CLEAR_DEBOUNCE_MS,
 *   giving new outputs a chance to arrive and replace the old ones
 *   without a visible flicker.
 */
function useDebouncedConsoleOutputs<T>(outputs: T[]): T[] {
  const [debouncedOutputs, setDebouncedOutputs] = useState(outputs);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Non-empty outputs: apply immediately and cancel any pending clear
  if (outputs.length > 0 && debouncedOutputs !== outputs) {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    setDebouncedOutputs(outputs);
  }

  // Empty outputs: delay the clear so new outputs can arrive first
  useEffect(() => {
    if (outputs.length === 0 && timerRef.current === null) {
      timerRef.current = setTimeout(() => {
        timerRef.current = null;
        setDebouncedOutputs([]);
      }, CONSOLE_CLEAR_DEBOUNCE_MS);
    }
    return () => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [outputs]);

  return debouncedOutputs;
}

interface Props {
  cellId: CellId;
  cellName: string;
  className?: string;
  consoleOutputs: WithResponse<OutputMessage>[];
  stale: boolean;
  debuggerActive: boolean;
  defaultExpanded?: boolean;
  onRefactorWithAI?: OnRefactorWithAI;
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
  const [isExpanded, setIsExpanded] = useExpandedConsoleOutput(
    props.cellId,
    props.defaultExpanded,
  );
  const [stdinValue, setStdinValue] = React.useState("");
  const inputHistory = useInputHistory({
    value: stdinValue,
    setValue: setStdinValue,
  });
  const {
    consoleOutputs: rawConsoleOutputs,
    stale,
    cellName,
    cellId,
    onSubmitDebugger,
    onClear,
    onRefactorWithAI,
    className,
  } = props;

  // Debounce clearing to prevent flickering when cells re-run
  const consoleOutputs = useDebouncedConsoleOutputs(rawConsoleOutputs);

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

  // Detect overflow on resize
  const isOverflowing = useOverflowDetection(ref, hasOutputs);

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

  const reversedOutputs = consoleOutputs.toReversed();
  const isPdb = reversedOutputs.some(
    (output) =>
      typeof output.data === "string" && output.data.includes("(Pdb)"),
  );

  // Find the index of the last stdin output since we only want to show
  // the pdb prompt once
  const lastStdInputIdx = reversedOutputs.findIndex(
    (output) => output.channel === "stdin",
  );

  const getOutputString = (): string => {
    const text = consoleOutputs
      .filter((output) => output.channel !== "pdb")
      .map((output) => processOutput(output))
      .join("\n");
    return text;
  };

  return (
    <div className="relative group">
      {hasOutputs && (
        <div className="absolute top-1 right-4 z-10 opacity-0 group-hover:opacity-100 flex items-center gap-1 print:hidden">
          <CopyClipboardIcon
            tooltip="Copy console output"
            value={getOutputString}
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
          {(isOverflowing || isExpanded) && (
            <Button
              aria-label={isExpanded ? "Collapse output" : "Expand output"}
              className="p-0 mb-px"
              onClick={() => setIsExpanded(!isExpanded)}
              size="xs"
              variant={null}
            >
              {isExpanded ? (
                <Tooltip content="Collapse output">
                  <ChevronsDownUpIcon className="h-4 w-4" />
                </Tooltip>
              ) : (
                <Tooltip content="Expand output">
                  <ChevronsUpDownIcon className="h-4 w-4 " />
                </Tooltip>
              )}
            </Button>
          )}
        </div>
      )}
      <div
        title={stale ? "This console output is stale" : undefined}
        data-testid="console-output-area"
        ref={ref}
        {...selectAllProps}
        // oxlint-ignore-next-line jsx-a11y/no-noninteractive-tabindex -- Needed to capture keypress events
        tabIndex={0}
        className={cn(
          "console-output-area overflow-hidden rounded-b-lg flex flex-col-reverse w-full gap-1 focus:outline-hidden",
          stale && "marimo-output-stale",
          hasOutputs ? "p-5" : "p-3",
          className,
        )}
        style={isExpanded ? { maxHeight: "none" } : undefined}
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
            const isPassword = output.mimetype === "text/password";

            if (output.response == null && lastStdInputIdx === idx) {
              return (
                <StdInput
                  key={idx}
                  output={output.data}
                  isPdb={isPdb}
                  isPassword={isPassword}
                  onSubmit={(text) => onSubmitDebugger(text, originalIdx)}
                  onClear={onClear}
                  value={stdinValue}
                  setValue={setStdinValue}
                  inputHistory={inputHistory}
                />
              );
            }

            return (
              <StdInputWithResponse
                key={idx}
                output={output.data}
                response={output.response}
                isPassword={isPassword}
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
  isPdb: boolean;
  isPassword?: boolean;
  value: string;
  setValue: (value: string) => void;
  inputHistory: UseInputHistoryReturn;
}) => {
  const {
    value,
    setValue,
    inputHistory,
    output,
    isPassword,
    isPdb,
    onSubmit,
    onClear,
  } = props;
  const { navigateUp, navigateDown, addToHistory } = inputHistory;

  return (
    <div className="flex gap-2 items-center pt-2">
      {renderText(output)}
      <Input
        data-testid="console-input"
        // This is used in <StdinBlockingAlert> to find the input
        data-stdin-blocking={true}
        type={isPassword ? "password" : "text"}
        autoComplete="off"
        autoFocus={true}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        icon={<ChevronRightIcon className="w-5 h-5" />}
        className="m-0 h-8 focus-visible:shadow-xs-solid"
        placeholder="stdin"
        // Capture the keydown event for history navigation and submission
        onKeyDownCapture={(e) => {
          if (e.key === "ArrowUp") {
            navigateUp();
            e.preventDefault();
            return;
          }

          if (e.key === "ArrowDown") {
            navigateDown();
            e.preventDefault();
            return;
          }

          if (e.key === "Enter" && !e.shiftKey) {
            if (value) {
              addToHistory(value);
              onSubmit(value);
              setValue("");
            }
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
      {isPdb && <DebuggerControls onSubmit={onSubmit} onClear={onClear} />}
    </div>
  );
};

const StdInputWithResponse = (props: {
  output: string;
  response?: string;
  isPassword?: boolean;
}) => {
  return (
    <div className="flex gap-2 items-center">
      {renderText(props.output)}
      {!props.isPassword && (
        <span className="text-(--sky-11)">{props.response}</span>
      )}
    </div>
  );
};

const renderText = (text: string | null) => {
  if (!text) {
    return null;
  }

  return <RenderTextWithLinks text={text} />;
};
