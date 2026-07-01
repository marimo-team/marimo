/* Copyright 2026 Marimo. All rights reserved. */
import type React from "react";
import { cn } from "@/utils/cn";
import type { CellOutputPosition } from "../renderers/types";

/**
 * Side-by-side cell layout: the code editor and the cell output sit in two
 * equal columns inside the cell card.
 */

interface CellColumnsProps {
  outputPosition: Extract<CellOutputPosition, "left" | "right">;
  codeEditor: React.ReactNode;
  /** The cell output. Falsy when the cell has produced no output yet. */
  output: React.ReactNode;
  /** Cell-level chrome (drag handle, delete) anchored to the whole row. */
  children?: React.ReactNode;
}

/**
 * Renders a cell's editor and output as two columns. When there is no output,
 * the editor fills the row.
 */
export const CellColumns: React.FC<CellColumnsProps> = ({
  outputPosition,
  codeEditor,
  output,
  children,
}) => {
  const hasOutput = Boolean(output);
  return (
    <div
      className={cn(
        "cell-columns",
        outputPosition === "left" && "cell-columns--reverse",
        hasOutput && "cell-columns--with-output",
      )}
    >
      {codeEditor}
      {hasOutput && (
        <div className="cell-columns__divider" aria-hidden="true" />
      )}
      {output}
      {children}
    </div>
  );
};
