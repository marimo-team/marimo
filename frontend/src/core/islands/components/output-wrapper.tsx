/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { selectAtom } from "jotai/utils";
import { Loader2Icon } from "lucide-react";
import React, { type PropsWithChildren, useCallback } from "react";
import { OutputRenderer } from "@/components/editor/Output";
import { type NotebookState, notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { isOutputEmpty } from "@/core/cells/outputs";
import type { CellRuntimeState } from "@/core/cells/types";
import { IslandControls } from "./IslandControls";
import { useIslandControls } from "./useIslandControls";

/**
 * Props for MarimoOutputWrapper component
 */
export interface MarimoOutputWrapperProps {
  /**
   * ID of the cell being rendered
   */
  cellId: CellId;

  /**
   * Callback to get the current code for the cell
   */
  codeCallback: () => string;

  /**
   * Whether to always show the run button (e.g., when editor is present)
   */
  alwaysShowRun: boolean;

  /**
   * Initial/static HTML content to display
   */
  children: React.ReactNode;
}

/**
 * Wraps marimo cell output with interactive controls and status indicators.
 *
 * This component:
 * - Renders cell output from the runtime state
 * - Shows a loading spinner when the cell is running
 * - Provides controls to copy code and re-run the cell
 */
export const MarimoOutputWrapper: React.FC<MarimoOutputWrapperProps> = ({
  cellId,
  codeCallback,
  alwaysShowRun,
  children,
}) => {
  const controlsVisible = useIslandControls(alwaysShowRun);
  const selector = useCallback(
    (s: NotebookState) => s.cellRuntime[cellId],
    [cellId],
  );
  const runtime = useAtomValue(selectAtom(notebookAtom, selector));

  // If no runtime yet, show static content
  if (!runtime?.output) {
    return <div className="relative min-h-6 empty:hidden">{children}</div>;
  }

  // No output to display
  if (isOutputEmpty(runtime.output)) {
    return null;
  }

  return (
    <div className="relative min-h-6">
      <OutputRenderer message={runtime.output} />
      <RunningIndicator state={runtime} />
      <IslandControls
        cellId={cellId}
        codeCallback={codeCallback}
        visible={controlsVisible}
      />
    </div>
  );
};

/**
 * Shows a spinning indicator when the cell is running
 */
const RunningIndicator: React.FC<{ state: CellRuntimeState }> = ({ state }) => {
  if (state.status === "running") {
    return (
      <DelayRender>
        <div className="absolute top-1 right-1">
          <Loader2Icon className="animate-spin size-4" />
        </div>
      </DelayRender>
    );
  }

  return null;
};

/**
 * Delays rendering of children by 200ms using CSS animation
 */
const DelayRender: React.FC<PropsWithChildren> = ({ children }) => {
  return <div className="animate-delayed-show-200">{children}</div>;
};
