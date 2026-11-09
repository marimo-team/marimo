/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { Loader2Icon } from "lucide-react";
import React, { type PropsWithChildren, useEffect, useRef } from "react";
import { OutputRenderer } from "@/components/editor/Output";
import type { CellId } from "@/core/cells/ids";
import { isOutputEmpty } from "@/core/cells/outputs";
import {
  type CellRunStatus,
  useCellExecution,
  useCellOutput,
} from "@/core/executions";
import { ISLAND_TAG_NAMES } from "../constants";
import { islandsHydratedAtom } from "../state";
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
  const wrapperRef = useRef<HTMLDivElement>(null);
  const output = useCellOutput(cellId);
  const isHydrated = useAtomValue(islandsHydratedAtom);

  // Sync cell status to the host <marimo-island> element as a data attribute
  // so downstream consumers can style based on status (e.g. [data-status="running"])
  const { status } = useCellExecution(cellId);
  useSyncStatusToIsland(wrapperRef, status);

  // Show the static content until the host has an output to replace it.
  // Keep static content mounted while the initial run is pending.
  if (!isHydrated || output === null) {
    return (
      <div ref={wrapperRef} className="relative min-h-6 empty:hidden">
        {children}
      </div>
    );
  }

  // No output to display
  if (isOutputEmpty(output)) {
    return <div ref={wrapperRef} />;
  }

  return (
    <div ref={wrapperRef} className="relative min-h-6">
      <OutputRenderer message={output} />
      <RunningIndicator status={status} />
      <IslandControls
        cellId={cellId}
        codeCallback={codeCallback}
        visible={controlsVisible}
      />
    </div>
  );
};

/**
 * Sets `data-status` on the closest `<marimo-island>` ancestor whenever the
 * cell's runtime status changes. This lets page authors style islands with
 * CSS like `marimo-island[data-status="running"] { opacity: 0.5; }`.
 */
function useSyncStatusToIsland(
  ref: React.RefObject<HTMLDivElement | null>,
  status: string,
) {
  useEffect(() => {
    const island = ref.current?.closest(ISLAND_TAG_NAMES.ISLAND);
    island?.setAttribute("data-status", status);
  }, [ref, status]);
}

/**
 * Shows a spinning indicator when the cell is running
 */
const RunningIndicator: React.FC<{ status: CellRunStatus }> = ({ status }) => {
  if (status === "running") {
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
