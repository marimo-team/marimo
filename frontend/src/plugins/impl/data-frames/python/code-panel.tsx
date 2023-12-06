/* Copyright 2023 Marimo. All rights reserved. */
import React from "react";
import { Transformations } from "../schema";
import { pythonPrintTransforms } from "./python-print";
import { ReadonlyPythonCode } from "@/components/editor/code/readonly-python-code";

interface Props {
  dataframeName: string;
  transforms?: Transformations;
}

export const CodePanel: React.FC<Props> = ({ transforms, dataframeName }) => {
  if (!transforms) {
    return null;
  }

  return (
    <ReadonlyPythonCode
      className="min-h-[200px]"
      minHeight="200px"
      code={pythonPrintTransforms(dataframeName, transforms.transforms)}
    />
  );
};
