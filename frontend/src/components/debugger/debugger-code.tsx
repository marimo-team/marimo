/* Copyright 2023 Marimo. All rights reserved. */
import { langs } from "@uiw/codemirror-extensions-langs";
import ReactCodeMirror from "@uiw/react-codemirror";
import React from "react";
import { Tooltip } from "../ui/tooltip";
import {
  ArrowDownIcon,
  ArrowUpIcon,
  HelpCircleIcon,
  LayersIcon,
  PlayIcon,
  SkipForwardIcon,
} from "lucide-react";
import { Button } from "../ui/button";
import { cn } from "@/utils/cn";

interface Props {
  code: string;
  onSubmit: (code: string) => void;
}

export const Debugger: React.FC<Props> = ({ code, onSubmit }) => {
  return (
    <div className="flex flex-col w-full border rounded overflow-hidden">
      <DebuggerOutput code={code} />
      <DebuggerControls onSubmit={onSubmit} />
      <DebuggerInput onSubmit={onSubmit} />
    </div>
  );
};

const DebuggerOutput: React.FC<{
  code: string;
}> = (props) => {
  return (
    <ReactCodeMirror
      height="200px"
      theme="dark"
      className={`[&>*]:outline-none overflow-hidden dark`}
      value={props.code}
      readOnly={true}
      basicSetup={{
        lineNumbers: false,
      }}
      extensions={[langs.shell()]}
    />
  );
};

const DebuggerInput: React.FC<{
  onSubmit: (code: string) => void;
}> = ({ onSubmit }) => {
  const [value, setValue] = React.useState("");

  return (
    <ReactCodeMirror
      minHeight="18px"
      theme="dark"
      className={`[&>*]:outline-none overflow-hidden`}
      value={value}
      basicSetup={{
        lineNumbers: false,
      }}
      extensions={[langs.python()]}
      onChange={(value) => setValue(value)}
      onKeyDown={(e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          onSubmit(value);
          setValue("");
        }
      }}
    />
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
          onClick={() => onSubmit("n")}
          className={cn(
            buttonClasses,
            "text-[var(--grass-11)] hover:text-[var(--grass-11)] hover:bg-[var(--grass-3)] hover:border-[var(--grass-8)]"
          )}
        >
          <PlayIcon fontSize={36} className={iconClasses} />
        </Button>
      </Tooltip>
      <Tooltip content="To upper frame">
        <Button
          variant="text"
          size="icon"
          className={buttonClasses}
          onClick={() => onSubmit("u")}
        >
          <ArrowUpIcon fontSize={36} className={iconClasses} />
        </Button>
      </Tooltip>
      <Tooltip content="To lower frame">
        <Button
          variant="text"
          size="icon"
          className={buttonClasses}
          onClick={() => onSubmit("d")}
        >
          <ArrowDownIcon fontSize={36} className={iconClasses} />
        </Button>
      </Tooltip>
      <Tooltip content="Print stack trace">
        <Button
          variant="text"
          size="icon"
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
          className={buttonClasses}
          onClick={() => onSubmit("help")}
        >
          <HelpCircleIcon fontSize={36} className={iconClasses} />
        </Button>
      </Tooltip>
    </div>
  );
};
