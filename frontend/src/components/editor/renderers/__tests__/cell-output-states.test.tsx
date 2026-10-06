/* Copyright 2026 Marimo. All rights reserved. */

import { act, render } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { Profiler } from "react";
import { describe, expect, it, vi } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import { notebookAtom } from "@/core/cells/cells";
import type { CellRuntimeState } from "@/core/cells/types";
import { connectionAtom } from "@/core/network/connection";
import { WebSocketState } from "@/core/websocket/types";
import type { Seconds } from "@/utils/time";
import { CellOutputStates } from "../cell-output-states";

const id = cellId("cell-a");
const richOutput = {
  channel: "output" as const,
  mimetype: "text/html" as const,
  data: "<div>rich</div>",
  timestamp: 2,
};

function setup(runtime: Partial<CellRuntimeState> = {}) {
  const store = createStore();
  store.set(connectionAtom, { state: WebSocketState.OPEN });
  store.set(
    notebookAtom,
    MockNotebook.notebookState({
      cellData: { [id]: {} },
      cellRuntime: { [id]: runtime },
    }),
  );
  const onRender = vi.fn();
  const { container } = render(
    <Provider store={store}>
      <Profiler id="output-states" onRender={onRender}>
        <CellOutputStates />
      </Profiler>
    </Provider>,
  );
  const readState = () =>
    container
      .querySelector("[data-cell-output-id]")
      ?.getAttribute("data-output-state");
  const update = (changes: Partial<CellRuntimeState>) =>
    act(() => {
      store.set(notebookAtom, (previous) => ({
        ...previous,
        cellRuntime: {
          ...previous.cellRuntime,
          [id]: { ...previous.cellRuntime[id], ...changes },
        },
      }));
    });
  return { store, container, readState, update, onRender };
}

describe("CellOutputStates", () => {
  it.each<[Partial<CellRuntimeState>, string]>([
    [{}, "unknown"],
    [
      { output: { channel: "output", mimetype: "text/plain", data: "" } },
      "empty",
    ],
    [{ output: richOutput }, "available"],
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
    [{ output: { ...richOutput, data: "" } }, "empty"],
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
    [{ output: richOutput, status: "running" }, "pending"],
    [{ output: richOutput, status: "queued" }, "pending"],
    ...[1, 2, 3].map<[Partial<CellRuntimeState>, string]>((started) => [
      {
        output: richOutput,
        status: "running",
        runStartTimestamp: started as Seconds,
      },
      started < richOutput.timestamp ? "available" : "pending",
    ]),
    [{ output: richOutput, status: "disabled-transitively" }, "available"],
    [{ output: { ...richOutput, data: "" }, status: "running" }, "pending"],
    [{ output: { ...richOutput, data: "" }, status: "queued" }, "pending"],
    [
      { output: { ...richOutput, data: "" }, status: "disabled-transitively" },
      "empty",
    ],
  ])("reports availability for %j", (runtime, expected) => {
    const { readState } = setup(runtime);
    expect(readState()).toBe(expected);
  });

  it("tracks execution without rendering another output", () => {
    const { container, readState, update } = setup({
      output: { channel: "output", mimetype: "text/plain", data: "" },
    });
    expect(readState()).toBe("empty");
    update({ status: "running", runStartTimestamp: 1 as Seconds });
    expect(readState()).toBe("pending");
    update({ output: richOutput });
    expect(readState()).toBe("available");
    update({ status: "idle" });
    expect(readState()).toBe("available");
    expect(container.textContent).toBe("");
    expect(container.firstElementChild?.hasAttribute("hidden")).toBe(true);
  });

  it("waits for fresh output when rerunning a cell", () => {
    const { readState, update } = setup({ output: richOutput });
    expect(readState()).toBe("available");
    update({ status: "queued" });
    expect(readState()).toBe("pending");
    update({ status: "running", runStartTimestamp: 3 as Seconds });
    expect(readState()).toBe("pending");
    update({ output: { ...richOutput, timestamp: 4 } });
    expect(readState()).toBe("available");
    update({ status: "idle", runStartTimestamp: null });
    expect(readState()).toBe("available");
  });

  it("does not rerender for console-only updates", () => {
    const { onRender, update } = setup({ output: richOutput });
    onRender.mockClear();
    update({
      consoleOutputs: [
        { channel: "stdout", mimetype: "text/plain", data: "progress" },
      ],
    });
    expect(onRender).not.toHaveBeenCalled();
  });

  it("does not trust cached output while disconnected", () => {
    const { store, readState } = setup({
      output: { channel: "output", mimetype: "text/plain", data: "" },
    });
    expect(readState()).toBe("empty");
    act(() => store.set(connectionAtom, { state: WebSocketState.CONNECTING }));
    expect(readState()).toBe("unknown");
  });
});
