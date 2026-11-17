/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import type { CellExecutionView, CellOutput } from "@/core/executions";
import { connectionAtom } from "@/core/network/connection";
import { ConnectionState } from "@/core/session/types";
import { getCellOutputState, installCaptureInterface } from "../capture";
import { notebookAtom } from "../cells";

const id = cellId("capture-a");
const settled = { status: "idle", rendered: false, outcome: "value" } as const;
const output: CellOutput = {
  channel: "output",
  mimetype: "text/html",
  data: "<div>rich</div>",
  timestamp: 2,
};

afterEach(() => {
  delete window.__marimoCapture;
});

describe("live output availability", () => {
  it("reads current host state without requiring DOM or subscribing to cells", () => {
    const store = createStore();
    store.set(connectionAtom, { state: ConnectionState.OPEN });
    const subscribe = vi.spyOn(store, "sub");
    installCaptureInterface(store);
    const query = () => window.__marimoCapture!.getCellState(id);
    expect(query()).toBe("missing");
    store.set(
      notebookAtom,
      MockNotebook.notebookState({ cellData: { [id]: {} } }),
    );
    MockExecutions.seed(store, []);
    expect(query()).toBe("unknown");
    MockExecutions.seed(store, [MockExecutions.completed(id)]);
    expect(query()).toBe("empty");
    MockExecutions.seed(store, [
      MockExecutions.shown(id, {
        mimetype: "text/html",
        data: "<div>rich</div>",
      }),
    ]);
    expect(query()).toBe("available");
    MockExecutions.seed(store, [MockExecutions.queued(id)]);
    expect(query()).toBe("pending");
    store.set(connectionAtom, { state: ConnectionState.CONNECTING });
    expect(query()).toBe("unknown");
    expect(subscribe).not.toHaveBeenCalled();
    subscribe.mockRestore();
  });
});

describe("cell output state", () => {
  it.each<
    [
      CellOutput | null,
      Pick<CellExecutionView, "status" | "rendered" | "outcome">,
      string,
    ]
  >([
    [null, { ...settled, outcome: null }, "unknown"],
    [null, settled, "empty"],
    [{ ...output, data: "" }, settled, "empty"],
    [output, settled, "available"],
    [output, { ...settled, status: "queued" }, "pending"],
    [output, { ...settled, status: "running" }, "pending"],
    [output, { ...settled, status: "running", rendered: true }, "available"],
    [
      { ...output, data: "" },
      { ...settled, status: "running", rendered: true },
      "pending",
    ],
  ])("reports availability for %j with %j", (output, execution, expected) => {
    expect(getCellOutputState(output, execution)).toBe(expected);
  });

  it.each([
    {},
    [{}, {}],
    { __metadata__: {} },
    [{ __metadata__: {} }, {}],
    "{}",
    "[{}, {}]",
    '{"__metadata__":{}}',
  ])("recognizes empty MIME bundles: %j", (data) => {
    expect(
      getCellOutputState(
        { ...output, mimetype: "application/vnd.marimo+mimebundle", data },
        settled,
      ),
    ).toBe("empty");
  });

  it("recognizes display entries in MIME bundles", () => {
    expect(
      getCellOutputState(
        {
          ...output,
          mimetype: "application/vnd.marimo+mimebundle",
          data: { "text/html": "<div>rich</div>", "image/png": "fallback" },
        },
        settled,
      ),
    ).toBe("available");
  });
});
