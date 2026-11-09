/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
import { cellId } from "@/__tests__/branded";
import {
  cell,
  document as documentOf,
  withCells,
} from "@/core/notebook/document/__tests__/fixtures";
import { clearCellOutputs } from "../atoms";
import { useCellFreshness, useCellOutput } from "../hooks";

const C1 = cellId("c1");
const C2 = cellId("c2");

/** A completed execution of `id` whose source matches the fixture document. */
function ran(id: string) {
  return MockExecutions.completed(id, { code_fingerprint: `${id}-hash` });
}

function setup(records: ReturnType<typeof ran>[]) {
  const store = createStore();
  const document = documentOf();
  const replica = MockExecutions.seed(store, records, null, document);
  const wrapper = ({ children }: { children: ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );
  return { store, document, replica, wrapper };
}

describe("useCellFreshness", () => {
  it("is current for a cell that never completed", () => {
    const { wrapper } = setup([]);
    const { result } = renderHook(() => useCellFreshness(C1), { wrapper });
    expect(result.current).toEqual({
      sourceChanged: false,
      inputsChanged: false,
    });
  });

  it("is current until the confirmed document arrives", () => {
    const store = createStore();
    MockExecutions.seed(store, [ran(C1)], null, null);
    const wrapper = ({ children }: { children: ReactNode }) => (
      <Provider store={store}>{children}</Provider>
    );
    const { result } = renderHook(() => useCellFreshness(C1), { wrapper });
    expect(result.current).toEqual({
      sourceChanged: false,
      inputsChanged: false,
    });
  });

  it("is current while the result's fingerprint matches the cell's", () => {
    const { wrapper } = setup([ran(C1)]);
    const { result } = renderHook(() => useCellFreshness(C1), { wrapper });
    expect(result.current).toEqual({
      sourceChanged: false,
      inputsChanged: false,
    });
  });

  it("reports changed source once the confirmed document carries it", () => {
    const { store, document, replica, wrapper } = setup([ran(C1)]);
    const { result } = renderHook(() => useCellFreshness(C1), { wrapper });

    act(() => {
      store.set(
        replica.documentAtom,
        withCells(document, {
          [C1]: cell(C1, "x = 2", { code_fingerprint: "c1-hash-2" }),
        }),
      );
    });

    expect(result.current).toEqual({
      sourceChanged: true,
      inputsChanged: false,
    });
  });

  it("leaves the cell alone when another cell's result changes", () => {
    const { store, replica, wrapper } = setup([ran(C1)]);
    let renders = 0;
    const { result } = renderHook(
      () => {
        renders += 1;
        return useCellFreshness(C1);
      },
      { wrapper },
    );
    const before = { value: result.current, renders };

    act(() => {
      const next = MockExecutions.inputs([ran(C1), ran(C2)]);
      store.set(replica.executionsAtom, next.executions);
      store.set(replica.resultsAtom, next.results);
    });

    expect(result.current).toBe(before.value);
    expect(renders).toBe(before.renders);
  });
});

describe("useCellOutput", () => {
  const shown = (id: string) =>
    MockExecutions.completed(id, {
      code_fingerprint: `${id}-hash`,
      outcome: {
        kind: "value",
        display: { mimetype: "text/plain", data: `${id} value` },
      },
    });

  it("reads the result's value and hides it once cleared, until a newer result", () => {
    const { store, replica, wrapper } = setup([shown(C1)]);
    const { result } = renderHook(() => useCellOutput(C1), { wrapper });
    expect(result.current?.data).toBe("c1 value");

    act(() => {
      clearCellOutputs(store, [C1]);
    });
    expect(result.current).toBeNull();

    act(() => {
      const next = MockExecutions.inputs([shown(C1)]);
      store.set(replica.executionsAtom, next.executions);
      store.set(replica.resultsAtom, next.results);
    });
    expect(result.current?.data).toBe("c1 value");
  });

  it("forgets what was cleared when the replica follows another notebook", () => {
    const { store, replica, wrapper } = setup([shown(C1)]);
    const { result } = renderHook(() => useCellOutput(C1), { wrapper });
    act(() => {
      clearCellOutputs(store, [C1]);
    });
    expect(result.current).toBeNull();

    act(() => {
      const notebook = store.get(replica.notebookAtom);
      store.set(replica.notebookAtom, { ...notebook, id: "n2" });
    });
    expect(result.current?.data).toBe("c1 value");
  });
});
