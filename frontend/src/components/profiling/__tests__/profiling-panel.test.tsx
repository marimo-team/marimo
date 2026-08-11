/* Copyright 2026 Marimo. All rights reserved. */
import { fireEvent, render, screen } from "@testing-library/react";
import { Provider } from "jotai";
import type React from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import {
  componentRenderCountAtom,
  profilerEventsAtom,
  profilingEnabledAtom,
} from "@/core/profiling/atoms";
import { store } from "@/core/state/jotai";
import { ProfilingPanel } from "../profiling-panel";

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <Provider store={store}>{children}</Provider>
);

describe("ProfilingPanel", () => {
  beforeEach(() => {
    store.set(profilingEnabledAtom, false);
    store.set(componentRenderCountAtom, {});
    store.set(profilerEventsAtom, []);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("shows empty state when profiling is disabled", () => {
    render(<ProfilingPanel />, { wrapper });
    expect(screen.getByText("Profiling disabled")).toBeTruthy();
    expect(screen.getByText(/profile=1/)).toBeTruthy();
  });

  test("shows render counts and totals when enabled", () => {
    store.set(profilingEnabledAtom, true);
    store.set(componentRenderCountAtom, { Cell: 5, OutputArea: 2 });

    render(<ProfilingPanel />, { wrapper });

    expect(screen.getByText("Total renders: 7")).toBeTruthy();
    expect(screen.getByText("Cell")).toBeTruthy();
    expect(screen.getByText("5")).toBeTruthy();
    expect(screen.getByText("OutputArea")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
  });

  test("Clear button resets all counters", () => {
    store.set(profilingEnabledAtom, true);
    store.set(componentRenderCountAtom, { Cell: 5 });

    render(<ProfilingPanel />, { wrapper });
    fireEvent.click(screen.getByTestId("reset-profiling-button"));

    expect(store.get(componentRenderCountAtom)).toEqual({});
  });

  test("Export JSON copies counters to the clipboard", () => {
    store.set(profilingEnabledAtom, true);
    store.set(componentRenderCountAtom, { Cell: 5 });
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    render(<ProfilingPanel />, { wrapper });
    fireEvent.click(screen.getByTestId("export-profiling-button"));

    expect(writeText).toHaveBeenCalledOnce();
    expect(JSON.parse(writeText.mock.calls[0][0])).toEqual(
      expect.objectContaining({ componentRenderCounts: { Cell: 5 } }),
    );
  });

  test("shows slowest renders rollup when profiler events exist", () => {
    store.set(profilingEnabledAtom, true);
    store.set(profilerEventsAtom, [
      {
        id: "Cell",
        phase: "update",
        actualDuration: 3,
        baseDuration: 10,
        timestamp: 1,
      },
      {
        id: "Cell",
        phase: "update",
        actualDuration: 5,
        baseDuration: 10,
        timestamp: 2,
      },
      {
        id: "OutputArea",
        phase: "update",
        actualDuration: 20,
        baseDuration: 30,
        timestamp: 3,
      },
    ]);

    render(<ProfilingPanel />, { wrapper });

    expect(screen.getByText("OutputArea")).toBeTruthy();
    expect(
      screen.getByText(
        /1 renders · 20\.0 ms total · avg 20\.0 ms · max 20\.0 ms/,
      ),
    ).toBeTruthy();
    expect(screen.getByText(/2 renders · 8\.0 ms total/)).toBeTruthy();
  });
});
