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

const ansiUp = new AnsiUp();

interface Props {
  cellId: CellId;
  cellName: string;
  className?: string;
  consoleOutputs: Array<WithResponse<OutputMessage>>;
  stale: boolean;
  debuggerActive: boolean;
  onRefactorWithAI?: (opts: { prompt: string }) => void;
  onSubmitDebugger: (text: string, index: number) => void;
}

export const ConsoleOutput = (props: Props): React.ReactNode => {
  const ref = React.useRef<HTMLDivElement>(null);
  const {
    consoleOutputs,
    stale,
    cellName,
    cellId,
    onSubmitDebugger,
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

  const renderText = (text: string) => {
    return (
      <span dangerouslySetInnerHTML={{ __html: ansiUp.ansi_to_html(text) }} />
    );
  };

  const reversedOutputs = [...consoleOutputs].reverse();

  return (
    <div
      title={stale ? "This console output is stale" : undefined}
      data-testid="console-output-area"
      ref={ref}
      className={cn(
        "console-output-area overflow-hidden rounded-b-lg flex flex-col-reverse w-full",
        stale && "marimo-output-stale",
        hasOutputs ? "p-5" : "p-3",
        className,
      )}
    >
      {reversedOutputs.map((output, idx) => {
        if (output.channel === "pdb") {
          return null;
        }
        const originalIdx = consoleOutputs.length - idx - 1;

        if (output.channel === "stdin") {
          invariant(
            typeof output.data === "string",
            "Expected data to be a string",
          );

          if (output.response == null) {
            return (
              <div key={idx} className="flex gap-2 items-center">
                {renderText(output.data)}
                <Input
                  data-testid="console-input"
                  type="text"
                  autoComplete="off"
                  autoFocus={true}
                  className="m-0"
                  placeholder="stdin"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      onSubmitDebugger(e.currentTarget.value, originalIdx);
                    }
                  }}
                />
              </div>
            );
          }
          return (
            <div key={idx} className="flex gap-2 items-center">
              {renderText(output.data)}
              <span className="text-[var(--sky-11)]">{output.response}</span>
            </div>
          );
        }

        return (
          <React.Fragment key={idx}>
            <OutputRenderer
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
