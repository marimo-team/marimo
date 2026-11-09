/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import { dequal } from "dequal";
import { useAtomValue } from "jotai";
import { selectAtom } from "jotai/utils";
import { useMemo } from "react";
import type { CellId } from "@/core/cells/ids";
import type { Outline } from "@/core/cells/outline";
import {
  cellExecutionInputsAtom,
  cellFreshnessAtom,
  cellOutlineAtom,
  cellOutputAtom,
  cellOutputInputsAtom,
} from "./atoms";
import type { CellFreshness } from "./freshness";
import { type CellOutput, scratchOutputView } from "./output";
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

/**
 * Whether a cell's result is current, by the host protocol's rules.
 *
 * The comparison reads the confirmed document, so an edit counts once the
 * host has it, not on the keystroke.
 */
export function useCellFreshness(id: Protocol.CellId): CellFreshness {
  const cellAtom = useMemo(
    () => selectAtom(cellFreshnessAtom, (freshness) => freshness(id), dequal),
    [id],
  );
  return useAtomValue(cellAtom);
}

/** What the cell shows: its running value so far, else its result's outcome. */
export function useCellOutput(id: CellId): CellOutput | null {
  return useAtomValue(cellOutputAtom(id));
}

/** The headings in the cell's output, for the table of contents. */
export function useCellOutline(id: CellId): Outline | null {
  return useAtomValue(cellOutlineAtom(id));
}

/** What the scratchpad shows, from its latest scratch execution. */
export function useScratchOutput(): CellOutput | null {
  const scratchAtom = useMemo(
    () =>
      selectAtom(
        cellOutputInputsAtom,
        (inputs) => scratchOutputView(inputs.executions),
        dequal,
      ),
    [],
  );
  return useAtomValue(scratchAtom);
}
