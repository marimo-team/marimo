/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import { connectionAtom } from "@/core/network/connection";
import { WebSocketState } from "@/core/websocket/types";
import type { Seconds } from "@/utils/time";
import { getCellOutputState, installCaptureInterface } from "../capture";
import { notebookAtom } from "../cells";
import type { CellRuntimeState } from "../types";

const id = cellId("capture-a");

afterEach(() => {
  delete window.__marimoCapture;
});

describe("live output availability", () => {
  it("reads current state without requiring DOM or subscribing to cells", () => {
    const store = createStore();
    store.set(connectionAtom, { state: WebSocketState.OPEN });
    const subscribe = vi.spyOn(store, "sub");
    installCaptureInterface(store);
    const query = () => window.__marimoCapture!.getCellState(id);
    expect(query()).toBe("missing");
    const update = (runtime: Partial<CellRuntimeState>) =>
      store.set(
        notebookAtom,
        MockNotebook.notebookState({
          cellData: { [id]: {} },
          cellRuntime: { [id]: runtime },
        }),
      );
    update({});
    expect(query()).toBe("unknown");
    update({ output: { channel: "output", mimetype: "text/plain", data: "" } });
    expect(query()).toBe("empty");
    update({ output: stateTestOutput });
    expect(query()).toBe("available");
    update({ output: stateTestOutput, status: "queued" });
    expect(query()).toBe("pending");
    store.set(connectionAtom, { state: WebSocketState.CONNECTING });
    expect(query()).toBe("unknown");
    expect(subscribe).not.toHaveBeenCalled();
    subscribe.mockRestore();
  });

  it.each(["{}", "[{}, {}]", '{"__metadata__":{}}'])(
    "recognizes JSON-encoded empty MIME bundles: %s",
    (data) => {
      const notebook = MockNotebook.notebookState({
        cellData: { [id]: {} },
        cellRuntime: {
          [id]: {
            output: {
              channel: "output",
              mimetype: "application/vnd.marimo+mimebundle",
              data,
            },
          },
        },
      });
      expect(getCellOutputState(notebook.cellRuntime[id])).toBe("empty");
    },
  );
});

const stateTestOutput = {
  channel: "output" as const,
  mimetype: "text/html" as const,
  data: "<div>rich</div>",
  timestamp: 2,
};

describe("cell output state", () => {
  it.each<[Partial<CellRuntimeState>, string]>([
    [{}, "unknown"],
    [
      { output: { channel: "output", mimetype: "text/plain", data: "" } },
      "empty",
    ],
    [{ output: stateTestOutput }, "available"],
    [
      {
        output: {
          channel: "output",
          mimetype: "application/vnd.marimo+mimebundle",
          data: {},
        },
      },
      "empty",
    ],
    [{ output: { ...stateTestOutput, data: "" } }, "empty"],
    ...[
      { __metadata__: { "image/png": { width: 10 } } },
      [{}, {}],
      [{ __metadata__: {} }, {}],
    ].map<[Partial<CellRuntimeState>, string]>((data) => [
      {
        output: {
          channel: "output",
          mimetype: "application/vnd.marimo+mimebundle",
          data,
        },
      },
      "empty",
    ]),
    [
      {
        output: {
          channel: "output",
          mimetype: "application/vnd.marimo+mimebundle",
          data: { "text/html": "<div>rich</div>", "image/png": "fallback" },
        },
      },
      "available",
    ],
    [{ output: stateTestOutput, status: "running" }, "pending"],
    [{ output: stateTestOutput, status: "queued" }, "pending"],
    ...[1, 2, 3].map<[Partial<CellRuntimeState>, string]>((started) => [
      {
        output: stateTestOutput,
        status: "running",
        runStartTimestamp: started as Seconds,
      },
      started < stateTestOutput.timestamp ? "available" : "pending",
    ]),
    [{ output: stateTestOutput, status: "disabled-transitively" }, "available"],
    [
      { output: { ...stateTestOutput, data: "" }, status: "running" },
      "pending",
    ],
    [{ output: { ...stateTestOutput, data: "" }, status: "queued" }, "pending"],
    [
      {
        output: { ...stateTestOutput, data: "" },
        status: "disabled-transitively",
      },
      "empty",
    ],
  ])("reports availability for %j", (runtime, expected) => {
    const state = MockNotebook.notebookState({
      cellData: { [id]: {} },
      cellRuntime: { [id]: runtime },
    });
    expect(getCellOutputState(state.cellRuntime[id])).toBe(expected);
  });
});
