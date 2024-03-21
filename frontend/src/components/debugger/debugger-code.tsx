/* Copyright 2024 Marimo. All rights reserved. */
import { langs } from "@uiw/codemirror-extensions-langs";
import ReactCodeMirror, {
  EditorView,
  Prec,
  ReactCodeMirrorRef,
  keymap,
} from "@uiw/react-codemirror";
import React, { memo } from "react";
import { Tooltip } from "../ui/tooltip";
import {
  HelpCircleIcon,
  LayersIcon,
  PlayIcon,
  SkipForwardIcon,
} from "lucide-react";
import { Button } from "../ui/button";
import { cn } from "@/utils/cn";
import "./debugger-code.css";
import { useKeydownOnElement } from "@/hooks/useHotkey";
import { Functions } from "@/utils/functions";

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
      className={`[&>*]:outline-none [&>.cm-editor]:pr-0 overflow-hidden dark`}
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

  // Capture some events to prevent default behavior
  useKeydownOnElement(ref.current, {
    ArrowUp: Functions.NOOP,
    ArrowDown: Functions.NOOP,
  });

  return (
    <div ref={ref}>
      <ReactCodeMirror
        minHeight="18px"
        theme="dark"
        className={`debugger-input [&>*]:outline-none cm-focused [&>.cm-editor]:pr-0 overflow-hidden dark border-t-4`}
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
                run: (view: EditorView) => {
                  const v = value.trim().replaceAll("\n", "\\n");
                  if (!v) {
                    return true;
                  }
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

const DebuggerControls: React.FC<{
  onSubmit: (code: string) => void;
}> = ({ onSubmit }) => {
  const buttonClasses =
    "border m-0 w-9 h-7 bg-[var(--blue-2)] text-[var(--slate-11)] hover:text-[var(--blue-11)] rounded-none border-[var(--blue-2)] hover:bg-[var(--sky-3)] hover:border-[var(--blue-8)]";
  const iconClasses = "w-5 h-5";

  return (
    <div className="flex">
      <Tooltip content="Next line">
        <Button
          variant="text"
          size="icon"
          data-testid="debugger-next-button"
          className={cn(buttonClasses, "rounded-bl-lg")}
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
            "text-[var(--grass-11)] hover:text-[var(--grass-11)] hover:bg-[var(--grass-3)] hover:border-[var(--grass-8)]",
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
    </div>
  );
};
