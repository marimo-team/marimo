/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import type { Transformations } from "../schema";
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
      minHeight="215px"
      maxHeight="215px"
      code={pythonPrintTransforms(dataframeName, transforms.transforms)}
    />
  );
};
