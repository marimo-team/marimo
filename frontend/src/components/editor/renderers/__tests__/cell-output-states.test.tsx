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
import { CellOutputStates } from "../cell-output-states";

const id = cellId("cell-a");
const richOutput = {
  channel: "output" as const,
  mimetype: "text/html" as const,
  data: "<div>rich</div>",
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
      "available",
    ],
    [{ output: { ...richOutput, data: "" } }, "empty"],
    [{ output: richOutput, status: "running" }, "available"],
    [{ output: richOutput, status: "queued" }, "available"],
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
    update({ status: "running" });
    expect(readState()).toBe("pending");
    update({ output: richOutput });
    expect(readState()).toBe("available");
    update({ status: "idle" });
    expect(readState()).toBe("available");
    expect(container.textContent).toBe("");
    expect(container.firstElementChild?.hasAttribute("hidden")).toBe(true);
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
