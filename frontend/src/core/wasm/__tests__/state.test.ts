/* Copyright 2024 Marimo. All rights reserved. */

import { createRef } from "react";
import { describe, expect, it } from "vitest";
import type { NotebookState } from "@/core/cells/cells";
import { notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { createCell, createCellRuntimeState } from "@/core/cells/types";
import type { OutputMessage } from "@/core/kernel/messages";
import { store } from "@/core/state/jotai";
import { CollapsibleTree, MultiColumn } from "@/utils/id-tree";
import { hasAnyOutputAtom } from "../state";

describe("hasAnyOutputAtom", () => {
  const createNotebookState = (
    outputs: Array<OutputMessage | null>,
  ): NotebookState => ({
    cellIds: new MultiColumn([
      CollapsibleTree.from(outputs.map((_, i) => `${i}` as CellId)),
    ]),
    cellData: Object.fromEntries(
      outputs.map((_, i) => [
        `${i}` as CellId,
        createCell({ id: `${i}` as CellId }),
      ]),
    ),
    cellRuntime: Object.fromEntries(
      outputs.map((output, i) => [
        `${i}` as CellId,
        createCellRuntimeState({
          output,
          status: "queued",
          outline: { items: [] },
        }),
      ]),
    ),
    cellHandles: Object.fromEntries(
      outputs.map((_, i) => [`${i}` as CellId, createRef()]),
    ),
    cellLogs: [],
    scrollKey: null,
    history: [],
  });

  it("should return false when there are no outputs", () => {
    store.set(notebookAtom, createNotebookState([null, null]));
    expect(store.get(hasAnyOutputAtom)).toBe(false);
  });

  it("should return false when all outputs are empty", () => {
    store.set(
      notebookAtom,
      createNotebookState([
        { channel: "output", mimetype: "text/plain", data: "", timestamp: 0 },
        { channel: "output", mimetype: "text/plain", data: "", timestamp: 0 },
      ]),
    );
    expect(store.get(hasAnyOutputAtom)).toBe(false);
  });

  it("should return true when there is at least one non-empty output", () => {
    store.set(
      notebookAtom,
      createNotebookState([
        { channel: "output", mimetype: "text/plain", data: "", timestamp: 0 },
        {
          channel: "output",
          mimetype: "text/plain",
          data: "hello",
          timestamp: 0,
        },
      ]),
    );
    expect(store.get(hasAnyOutputAtom)).toBe(true);
  });

  it("should handle various output types", () => {
    store.set(
      notebookAtom,
      createNotebookState([
        {
          channel: "output",
          mimetype: "application/json",
          data: { foo: "bar" },
          timestamp: 0,
        },
        { channel: "output", mimetype: "text/plain", data: "", timestamp: 0 },
      ]),
    );
    expect(store.get(hasAnyOutputAtom)).toBe(true);
  });

  it("should return true when all outputs are idle", () => {
    const notebookState = createNotebookState([null, null]);
    const cellId0 = "0" as CellId;
    const cellId1 = "1" as CellId;
    // Some idle cell, so returns false
    store.set(notebookAtom, {
      ...notebookState,
      cellRuntime: {
        ...notebookState.cellRuntime,
        [cellId0]: {
          ...notebookState.cellRuntime[cellId0],
          status: "idle",
        },
      },
    });
    expect(store.get(hasAnyOutputAtom)).toBe(false);

    // All cells are idle, so returns true
    store.set(notebookAtom, {
      ...notebookState,
      cellRuntime: {
        [cellId0]: {
          ...notebookState.cellRuntime[cellId0],
          status: "idle",
        },
        [cellId1]: {
          ...notebookState.cellRuntime[cellId1],
          status: "idle",
        },
      },
    });
    expect(store.get(hasAnyOutputAtom)).toBe(true);
  });
});
