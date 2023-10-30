/* Copyright 2023 Marimo. All rights reserved. */
import React from "react";
import { Transformations } from "../schema";
import { python } from "@codemirror/lang-python";
import CodeMirror from "@uiw/react-codemirror";
import { pythonPrintTransforms } from "./python-print";
import { CopyIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Events } from "@/utils/events";
import { toast } from "@/components/ui/use-toast";

interface Props {
  dataframeName: string;
  transforms?: Transformations;
}

export const CodePanel: React.FC<Props> = ({ transforms, dataframeName }) => {
  if (!transforms) {
    return null;
  }

  return (
    <PythonCode
      code={pythonPrintTransforms(dataframeName, transforms.transforms)}
    />
  );
};

const PythonCode = (props: { code: string }) => {
  return (
    <div className="relative min-h-[200px]">
      <FloatingCopyButton text={props.code} />
      <CodeMirror
        minHeight="200px"
        height="100%"
        editable={true}
        extensions={[python()]}
        value={props.code}
        readOnly={true}
      />
    </div>
  );
};

const FloatingCopyButton = (props: { text: string }) => {
  const copy = Events.stopPropagation(() => {
    navigator.clipboard.writeText(props.text);
    toast({ title: "Copied to clipboard" });
  });

  return (
    <Button
      onClick={copy}
      className="absolute top-0 right-0 m-2 z-10"
      variant="secondary"
    >
      <CopyIcon size={16} strokeWidth={1.5} />
    </Button>
  );
};
