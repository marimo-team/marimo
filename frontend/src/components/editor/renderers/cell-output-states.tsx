/* Copyright 2026 Marimo. All rights reserved. */

import { atom, useAtomValue } from "jotai";
import { memo, useMemo } from "react";
import { outputIsLoading } from "@/core/cells/cell";
import { notebookAtom, useCellIds } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { isOutputEmpty } from "@/core/cells/outputs";
import type { CellRuntimeState } from "@/core/cells/types";
import { isConnectedAtom } from "@/core/network/connection";

/** Kiosk capture metadata must remain available even when a layout omits a cell. */
export const CellOutputStates = () => {
  const cellIds = useCellIds();
  const connected = useAtomValue(isConnectedAtom);
  return (
    <div hidden={true}>
      {cellIds.inOrderIds.map((cellId) => (
        <CellOutputState key={cellId} cellId={cellId} connected={connected} />
      ))}
    </div>
  );
};

type OutputState = "unknown" | "pending" | "empty" | "available";

function getOutputState(runtime: CellRuntimeState | undefined): OutputState {
  if (!runtime) {
    return "unknown";
  }
  const loading = outputIsLoading(runtime.status);
  // Retained output belongs to the previous run; streamed progress is fresh.
  const outputReceivedWhileRunning =
    runtime.status === "running" &&
    runtime.runStartTimestamp !== null &&
    (runtime.output?.timestamp ?? 0) > runtime.runStartTimestamp;
  if (loading && !outputReceivedWhileRunning) {
    return "pending";
  }
  if (!isOutputEmpty(runtime.output)) {
    return "available";
  }
  if (loading) {
    return "pending";
  }
  // A default idle state with no output may precede session replay.
  return runtime.output === null ? "unknown" : "empty";
}

const CellOutputState = memo(
  ({ cellId, connected }: { cellId: CellId; connected: boolean }) => {
    const outputState = useAtomValue(
      useMemo(
        () =>
          atom((get) => getOutputState(get(notebookAtom).cellRuntime[cellId])),
        [cellId],
      ),
    );
    const state = connected ? outputState : "unknown";
    return <span data-cell-output-id={cellId} data-output-state={state} />;
  },
);
CellOutputState.displayName = "CellOutputState";
