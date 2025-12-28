/* Copyright 2026 Marimo. All rights reserved. */
import { langs } from "@uiw/codemirror-extensions-langs";
import ReactCodeMirror, {
  EditorView,
  keymap,
  Prec,
  type ReactCodeMirrorRef,
} from "@uiw/react-codemirror";
import {
  HelpCircleIcon,
  LayersIcon,
  PlayIcon,
  SkipForwardIcon,
  TrashIcon,
} from "lucide-react";
import React, { memo } from "react";
import { cn } from "@/utils/cn";
import { Button } from "../ui/button";
import { Tooltip } from "../ui/tooltip";
import "./debugger-code.css";
import { useKeydownOnElement } from "@/hooks/useHotkey";

interface Props {
  code: string;
  onSubmit: (code: string) => void;
}

export const Debugger: React.FC<Props> = ({ code, onSubmit }) => {
  return (
    <div className="flex flex-col w-full rounded-b overflow-hidden">
      <DebuggerOutput code={code} />
      <DebuggerInput onSubmit={onSubmit} />
      <DebuggerControls onSubmit={onSubmit} />
    </div>
  );
};

const DebuggerOutput: React.FC<{
  code: string;
}> = memo((props) => {
  const ref = React.useRef<ReactCodeMirrorRef>({});

  return (
    <ReactCodeMirror
      minHeight="200px"
      maxHeight="200px"
      ref={ref}
      theme="dark"
      value={props.code}
      className={"*:outline-hidden [&>.cm-editor]:pr-0 overflow-hidden dark"}
      readOnly={true}
      editable={false}
      basicSetup={{
        lineNumbers: false,
      }}
      extensions={[
        langs.shell(),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) {
            ref.current.view?.dispatch({
              selection: {
                anchor: update.state.doc.length,
                head: update.state.doc.length,
              },
              scrollIntoView: true,
            });
          }
        }),
      ]}
    />
  );
});
DebuggerOutput.displayName = "DebuggerOutput";

const DebuggerInput: React.FC<{
  onSubmit: (code: string) => void;
}> = ({ onSubmit }) => {
  const [value, setValue] = React.useState("");
  const ref = React.useRef<HTMLDivElement>(null);

  // Command history state
  const historyRef = React.useRef<string[]>([]);
  const historyIndexRef = React.useRef<number>(-1);
  // Store the current input when navigating history
  const pendingInputRef = React.useRef<string>("");

  const navigateHistory = React.useCallback(
    (direction: "up" | "down") => {
      const history = historyRef.current;
      if (history.length === 0) {
        return;
      }

      const currentIndex = historyIndexRef.current;

      if (direction === "up") {
        // Save current input if we're starting to navigate
        if (currentIndex === -1) {
          pendingInputRef.current = value;
        }
        // Navigate to previous command
        const newIndex = Math.min(currentIndex + 1, history.length - 1);
        if (newIndex !== currentIndex) {
          historyIndexRef.current = newIndex;
          setValue(history[history.length - 1 - newIndex]);
        }
      } else {
        // Navigate to next command
        if (currentIndex > 0) {
          const newIndex = currentIndex - 1;
          historyIndexRef.current = newIndex;
          setValue(history[history.length - 1 - newIndex]);
        } else if (currentIndex === 0) {
          // Return to pending input
          historyIndexRef.current = -1;
          setValue(pendingInputRef.current);
        }
      }
    },
    [value],
  );

  // Capture some events for command history navigation
  useKeydownOnElement(ref, {
    ArrowUp: () => navigateHistory("up"),
    ArrowDown: () => navigateHistory("down"),
  });

  return (
    <div ref={ref}>
      <ReactCodeMirror
        minHeight="18px"
        theme="dark"
        className={
          "debugger-input *:outline-hidden cm-focused [&>.cm-editor]:pr-0 overflow-hidden dark border-t-4"
        }
        value={value}
        autoFocus={true}
        basicSetup={{
          lineNumbers: false,
        }}
        extensions={[
          langs.python(),
          Prec.highest(
            keymap.of([
              {
                key: "Enter",
                preventDefault: true,
                stopPropagation: true,
                run: () => {
                  const v = value.trim().replaceAll("\n", "\\n");
                  if (!v) {
                    return true;
                  }
                  // Add to history if it's not a duplicate of the last command
                  const history = historyRef.current;
                  if (
                    history.length === 0 ||
                    history[history.length - 1] !== v
                  ) {
                    historyRef.current = [...history, v];
                  }
                  // Reset history navigation state
                  historyIndexRef.current = -1;
                  pendingInputRef.current = "";
                  onSubmit(v);
                  setValue("");
                  return true;
                },
              },
              {
                key: "Shift-Enter",
                preventDefault: true,
                stopPropagation: true,
                run: (view: EditorView) => {
                  // Insert newline and move cursor to end of line
                  view.dispatch({
                    changes: {
                      from: view.state.selection.main.to,
                      insert: "\n",
                    },
                  });

                  return true;
                },
              },
            ]),
          ),
        ]}
        onChange={(value) => setValue(value)}
      />
    </div>
  );
};

export const DebuggerControls: React.FC<{
  onSubmit: (code: string) => void;
  onClear?: () => void;
}> = ({ onSubmit, onClear }) => {
  const buttonClasses = cn(
    "m-0 w-9 h-8 bg-(--slate-2) text-(--slate-11) hover:text-(--blue-11) rounded-none hover:bg-(--sky-3) hover:border-(--blue-8)",
    "first:rounded-l-lg first:border-l border-t border-b hover:border",
    "last:rounded-r-lg last:border-r",
  );
  const iconClasses = "w-5 h-5";

  return (
    <div className="flex">
      <Tooltip content="Next line">
        <Button
          variant="text"
          size="icon"
          data-testid="debugger-next-button"
          className={buttonClasses}
          onClick={() => onSubmit("n")}
        >
          <SkipForwardIcon fontSize={36} className={iconClasses} />
        </Button>
      </Tooltip>
      <Tooltip content="Continue execution">
        <Button
          variant="text"
          size="icon"
          data-testid="debugger-continue-button"
          onClick={() => onSubmit("c")}
          className={cn(
            buttonClasses,
            "text-(--grass-11) hover:text-(--grass-11) hover:bg-(--grass-3) hover:border-(--grass-8)",
          )}
        >
          <PlayIcon fontSize={36} className={iconClasses} />
        </Button>
      </Tooltip>
      <Tooltip content="Print stack trace">
        <Button
          variant="text"
          size="icon"
          data-testid="debugger-stack-button"
          className={buttonClasses}
          onClick={() => onSubmit("bt")}
        >
          <LayersIcon fontSize={36} className={iconClasses} />
        </Button>
      </Tooltip>
      <Tooltip content="Help">
        <Button
          variant="text"
          size="icon"
          data-testid="debugger-help-button"
          className={buttonClasses}
          onClick={() => onSubmit("help")}
        >
          <HelpCircleIcon fontSize={36} className={iconClasses} />
        </Button>
      </Tooltip>
      {onClear && (
        <Tooltip content="Clear">
          <Button
            variant="text"
            size="icon"
            data-testid="debugger-clear-button"
            className={cn(
              buttonClasses,
              "text-(--red-11) hover:text-(--red-11) hover:bg-(--red-2) hover:border-(--red-8)",
            )}
            onClick={onClear}
          >
            <TrashIcon fontSize={36} className={iconClasses} />
          </Button>
        </Tooltip>
      )}
    </div>
  );
};
