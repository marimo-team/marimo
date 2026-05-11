/* Copyright 2026 Marimo. All rights reserved. */

import { isEmpty } from "lodash-es";
import React from "react";

interface ToolArgsRendererProps {
  input: unknown;
  label?: string;
}

export const ToolArgsRenderer: React.FC<ToolArgsRendererProps> = ({
  input,
  label = "Tool Request",
}) => {
  if (input == null) {
    return null;
  }

  const isEmptyInput = isEmpty(input);
  const isObject =
    typeof input === "object" &&
    !Array.isArray(input) &&
    Object.keys(input as Record<string, unknown>).length > 0;

  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold text-muted-foreground">{label}</h3>
      <pre className="bg-(--slate-2) p-2 text-muted-foreground border border-(--slate-4) rounded text-xs overflow-auto scrollbar-thin max-h-64">
        {isEmptyInput
          ? "{}"
          : isObject
            ? JSON.stringify(input, null, 2)
            : String(input)}
      </pre>
    </div>
  );
};
