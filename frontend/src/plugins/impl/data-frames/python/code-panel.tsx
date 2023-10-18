/* Copyright 2023 Marimo. All rights reserved. */
import React from "react";
import { Transformations } from "../schema";
import { python } from "@codemirror/lang-python";
import CodeMirror from "@uiw/react-codemirror";
import { pythonPrintTransforms } from "./python-print";

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
    <div className="border rounded overflow-hidden">
      <CodeMirror
        minHeight="100px"
        height="100%"
        editable={true}
        extensions={[python()]}
        value={props.code}
        readOnly={true}
      />
    </div>
  );
};
