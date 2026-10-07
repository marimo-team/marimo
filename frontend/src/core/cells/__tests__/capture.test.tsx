/* Copyright 2026 Marimo. All rights reserved. */

import { act, render } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { startTransition, Suspense } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import { OutputArea } from "@/components/editor/Output";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { OutputMessage } from "@/core/kernel/messages";
import { connectionAtom } from "@/core/network/connection";
import { WebSocketState } from "@/core/websocket/types";
import { getCellOutputState, installCaptureInterface } from "../capture";
import type { Seconds } from "@/utils/time";
import { notebookAtom } from "../cells";
import type { CellRuntimeState } from "../types";

const id = cellId("capture-a");
const oldOutput: OutputMessage = {
  channel: "output",
  mimetype: "text/plain",
  data: "old",
  timestamp: 1,
};
const newOutput: OutputMessage = { ...oldOutput, data: "new", timestamp: 3 };

const chartGate = vi.hoisted(() => ({
  blocked: false,
  promise: Promise.resolve(),
}));
vi.mock("@/components/charts/lazy", () => ({
  LazyVegaEmbed: ({ spec }: { spec: { description: string } }) => {
    if (spec.description === "new" && chartGate.blocked) {
      throw chartGate.promise;
    }
    return <div>{spec.description}</div>;
  },
}));

function setup(runtime?: Partial<CellRuntimeState>) {
  const store = createStore();
  store.set(connectionAtom, { state: WebSocketState.OPEN });
  store.set(
    notebookAtom,
    MockNotebook.notebookState({
      cellData: { [id]: {} },
      cellRuntime: { [id]: runtime ?? { output: oldOutput } },
    }),
  );
  installCaptureInterface(store);
  const query = () => window.__marimoCapture!.getCellState(id);
  const update = (changes: Partial<CellRuntimeState>) =>
    store.set(notebookAtom, (previous) => ({
      ...previous,
      cellRuntime: {
        ...previous.cellRuntime,
        [id]: { ...previous.cellRuntime[id], ...changes },
      },
    }));
  function View({
    output,
    expand = false,
  }: {
    output: OutputMessage;
    expand?: boolean;
  }) {
    return (
      <Provider store={store}>
        <TooltipProvider>
          <OutputArea
            output={output}
            cellId={id}
            stale={false}
            loading={false}
            allowExpand={expand}
          />
        </TooltipProvider>
      </Provider>
    );
  }
  return { store, query, update, View };
}

beforeEach(() => {
  const rect = new DOMRect(0, 0, 10, 10);
  vi.spyOn(HTMLElement.prototype, "getClientRects").mockReturnValue(
    Object.assign([rect], {
      item: (index: number) => (index === 0 ? rect : null),
    }),
  );
});
afterEach(() => {
  chartGate.blocked = false;
  delete window.__marimoCapture;
  vi.restoreAllMocks();
});

describe("mount-level capture interface", () => {
  it("does not accept an old chart retained by an inner Suspense boundary", async () => {
    const oldChart: OutputMessage = {
      ...oldOutput,
      mimetype: "application/vnd.vegalite.v6+json",
      data: { description: "old" },
    };
    const newChart: OutputMessage = {
      ...oldChart,
      data: { description: "new" },
      timestamp: 3,
    };
    const { View, query, update } = setup({ output: oldChart });
    const view = render(<View output={oldChart} />);
    expect(query()).toBe("ready");
    let release!: () => void;
    chartGate.promise = new Promise<void>((resolve) => {
      release = resolve;
    });
    chartGate.blocked = true;
    update({ output: newChart });
    act(() => startTransition(() => view.rerender(<View output={newChart} />)));
    expect(document.getElementById(`output-${id}`)?.textContent).toContain(
      "old",
    );
    expect(query()).toBe("pending");
    await act(async () => {
      chartGate.blocked = false;
      release();
      await chartGate.promise;
    });
    expect(query()).toBe("ready");
    expect(document.getElementById(`output-${id}`)?.textContent).toContain(
      "new",
    );
  });
  it.each([
    {},
    { __metadata__: {} },
    [{}, {}],
    "{}",
    "[{}, {}]",
    '{"__metadata__":{}}',
  ])("recognizes empty MIME bundles without a rendered cell: %j", (data) => {
    const { query } = setup({
      output: {
        ...oldOutput,
        mimetype: "application/vnd.marimo+mimebundle",
        data,
      },
    });
    expect(query()).toBe("empty");
  });
  it("distinguishes missing, unreplayed, empty, and disconnected cells without DOM", () => {
    const { store, query, update } = setup({});
    expect(window.__marimoCapture!.getCellState("absent")).toBe("missing");
    expect(query()).toBe("unknown");
    update({ output: { ...oldOutput, data: "" } });
    expect(query()).toBe("empty");
    store.set(connectionAtom, { state: WebSocketState.CONNECTING });
    expect(query()).toBe("unknown");
  });

  it.each([false, true])(
    "tracks the actual output commit, expandable=%s",
    (expand) => {
      const { View, query, update } = setup();
      const view = render(<View output={oldOutput} expand={expand} />);
      expect(query()).toBe("ready");
      update({ output: newOutput });
      expect(document.getElementById(`output-${id}`)?.textContent).toContain(
        "old",
      );
      expect(query()).toBe("pending");
      view.rerender(<View output={newOutput} expand={expand} />);
      expect(query()).toBe("ready");
      view.unmount();
      expect(query()).toBe("pending");
    },
  );

  it("waits through a suspended React transition while old DOM remains visible", async () => {
    const { View, query, update } = setup();
    let release!: () => void;
    let blocked = true;
    const promise = new Promise<void>((resolve) => {
      release = resolve;
    });
    function Deferred({ output }: { output: OutputMessage }) {
      if (output === newOutput && blocked) {
        throw promise;
      }
      return <View output={output} />;
    }
    const view = render(
      <Suspense fallback={<div>loading</div>}>
        <Deferred output={oldOutput} />
      </Suspense>,
    );
    expect(query()).toBe("ready");
    update({ output: newOutput });
    act(() =>
      startTransition(() =>
        view.rerender(
          <Suspense fallback={<div>loading</div>}>
            <Deferred output={newOutput} />
          </Suspense>,
        ),
      ),
    );
    expect(document.getElementById(`output-${id}`)?.textContent).toContain(
      "old",
    );
    expect(query()).toBe("pending");
    await act(async () => {
      blocked = false;
      release();
      await promise;
    });
    expect(query()).toBe("ready");
    expect(document.getElementById(`output-${id}`)?.textContent).toContain(
      "new",
    );
  });

  it("does not accept retained output during a rerun but accepts fresh progress", () => {
    const { View, query, update } = setup();
    const view = render(<View output={oldOutput} />);
    update({ status: "queued" });
    expect(query()).toBe("pending");
    update({
      status: "running",
      runStartTimestamp: 2 as NonNullable<
        CellRuntimeState["runStartTimestamp"]
      >,
    });
    expect(query()).toBe("pending");
    update({ output: newOutput });
    expect(query()).toBe("pending");
    view.rerender(<View output={newOutput} />);
    expect(query()).toBe("ready");
    update({ status: "disabled-transitively" });
    expect(query()).toBe("ready");
  });

  it("rejects untracked and hidden DOM even when it has content", () => {
    const { query, View } = setup();
    const fake = document.createElement("div");
    fake.id = `output-${id}`;
    fake.textContent = "old";
    document.body.append(fake);
    expect(query()).toBe("pending");
    fake.remove();
    render(<View output={oldOutput} />);
    expect(query()).toBe("ready");
    vi.mocked(HTMLElement.prototype.getClientRects).mockReturnValue(
      Object.assign([], { item: () => null }),
    );
    expect(query()).toBe("pending");
  });

  it("installs no subscriptions and reads live state on demand", () => {
    const { store, query, update } = setup({
      output: { ...oldOutput, data: "" },
    });
    const subscribe = vi.spyOn(store, "sub");
    installCaptureInterface(store);
    expect(query()).toBe("empty");
    update({
      consoleOutputs: [
        { channel: "stdout", mimetype: "text/plain", data: "progress" },
      ],
    });
    expect(query()).toBe("empty");
    expect(subscribe).not.toHaveBeenCalled();
  });

  it("treats a known cell awaiting runtime replay as unknown, not missing", () => {
    const { store, query } = setup();
    store.set(notebookAtom, (previous) => ({ ...previous, cellRuntime: {} }));
    expect(query()).toBe("unknown");
  });
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
