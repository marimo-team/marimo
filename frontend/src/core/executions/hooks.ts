/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import { dequal } from "dequal";
import { useAtomValue } from "jotai";
import { selectAtom } from "jotai/utils";
import { useMemo } from "react";
import { cellExecutionInputsAtom } from "./atoms";
import { type CellExecutionView, cellExecutionView } from "./select";

/**
 * A cell's status, timing, and how it last ended.
 *
 * Read from the host's executions, with the editor's own marks for a run
 * it has requested and the kernel has not planned yet, and for a cell the
 * kernel reports blocked by a disabled ancestor.
 */
export function useCellExecution(id: Protocol.CellId): CellExecutionView {
  // One atom per mounted cell, kept for its subscription and compared by
  // value so the cell renders only when its own view changes.
  const cellAtom = useMemo(
    () =>
      selectAtom(
        cellExecutionInputsAtom,
        (inputs) => cellExecutionView(inputs, id),
        dequal,
      ),
    [id],
  );
  return useAtomValue(cellAtom);
}
