/* Copyright 2026 Marimo. All rights reserved. */
import { fireEvent, render, screen } from "@testing-library/react";
import { Provider } from "jotai";
import type React from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import {
  componentRenderCountAtom,
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
});
