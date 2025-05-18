/* Copyright 2024 Marimo. All rights reserved. */
import React, { useLayoutEffect } from "react";
import type { OutputMessage } from "@/core/kernel/messages";
import { OutputRenderer } from "../Output";
import { cn } from "@/utils/cn";
import { isInternalCellName } from "@/core/cells/names";
import { NameCellContentEditable } from "../actions/name-cell-input";
import type { CellId } from "@/core/cells/ids";
import { Input } from "@/components/ui/input";
import { AnsiUp } from "ansi_up";
import type { WithResponse } from "@/core/cells/types";
import { invariant } from "@/utils/invariant";
import { ErrorBoundary } from "../boundary/ErrorBoundary";
import { DebuggerControls } from "@/components/debugger/debugger-code";
import { ChevronRightIcon } from "lucide-react";

const ansiUp = new AnsiUp();

interface Props {
  cellId: CellId;
  cellName: string;
  className?: string;
  consoleOutputs: Array<WithResponse<OutputMessage>>;
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

  return (
    <div
      title={stale ? "This console output is stale" : undefined}
      data-testid="console-output-area"
      ref={ref}
      className={cn(
        "console-output-area overflow-hidden rounded-b-lg flex flex-col-reverse w-full gap-1",
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
            />
          </React.Fragment>
        );
      })}
      <NameCellContentEditable
        value={cellName}
        cellId={cellId}
        className="bg-[var(--slate-4)] border-[var(--slate-4)] hover:bg-[var(--slate-5)] dark:border-[var(--sky-5)] dark:bg-[var(--sky-6)] dark:text-[var(--sky-12)] text-[var(--slate-12)] rounded-tl rounded-br-lg absolute right-0 bottom-0 text-xs px-1.5 py-0.5 font-mono"
      />
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
        className="m-0 h-8 focus-visible:shadow-xsSolid"
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

const StdInputWithResponse = (props: {
  output: string;
  response?: string;
}) => {
  return (
    <div className="flex gap-2 items-center">
      {renderText(props.output)}
      <span className="text-[var(--sky-11)]">{props.response}</span>
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
