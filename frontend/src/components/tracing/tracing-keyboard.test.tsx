/* Copyright 2026 Marimo. All rights reserved. */

import { act, fireEvent, render, screen } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { type Run, type RunId, runsAtom } from "@/core/cells/runs";
import { Tracing } from "./tracing";

vi.mock("react-vega", () => ({ useVegaEmbed: () => undefined }));
vi.mock("vega-lite", () => ({ compile: () => ({ spec: {} }) }));
vi.mock("@/components/editor/chrome/panels/panel-context", () => ({
  usePanelSection: () => "sidebar",
}));

const run: Run = {
  runId: "run-1" as RunId,
  runStartTime: 1_704_067_200,
  cellRuns: new Map(),
};

describe("trace disclosure keyboard focus", () => {
  it.each([false, true])(
    "keeps the header focused across toggles (inline=%s)",
    (inline) => {
      const store = createStore();
      store.set(runsAtom, {
        runIds: [run.runId],
        runMap: new Map([[run.runId, run]]),
      });
      render(
        <Provider store={store}>
          <TooltipProvider>
            <Tracing />
          </TooltipProvider>
        </Provider>,
      );
      if (inline) {
        fireEvent.click(screen.getByRole("checkbox", { name: "Inline chart" }));
      }
      const header = screen.getByRole("button", { name: /^Run -/ });
      act(() => header.focus());
      for (const expanded of [false, true, false]) {
        // Native buttons emit a click with detail=0 for keyboard activation.
        fireEvent.click(header, { detail: 0 });
        expect(screen.getByRole("button", { name: /^Run -/ })).toBe(header);
        expect(header).toHaveFocus();
        expect(header).toHaveAttribute("aria-expanded", String(expanded));
      }
    },
  );

  it("does not steal focus when a newer run expands automatically", () => {
    const store = createStore();
    store.set(runsAtom, {
      runIds: [run.runId],
      runMap: new Map([[run.runId, run]]),
    });
    render(
      <Provider store={store}>
        <TooltipProvider>
          <Tracing />
        </TooltipProvider>
      </Provider>,
    );
    const header = screen.getByRole("button", { name: /^Run -/ });
    act(() => header.focus());
    const newer: Run = {
      ...run,
      runId: "run-2" as RunId,
      runStartTime: run.runStartTime + 1,
    };
    act(() => {
      store.set(runsAtom, {
        runIds: [newer.runId, run.runId],
        runMap: new Map([
          [run.runId, run],
          [newer.runId, newer],
        ]),
      });
    });
    expect(header).toHaveFocus();
    expect(header).toHaveAttribute("aria-expanded", "false");
  });
});
