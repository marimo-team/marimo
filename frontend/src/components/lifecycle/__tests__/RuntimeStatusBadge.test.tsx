/* Copyright 2026 Marimo. All rights reserved. */

import { act, render, screen } from "@testing-library/react";
import { atom, createStore, Provider } from "jotai";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import {
  type AdapterState,
  type RuntimeAdapter,
  runtimeAdapterAtom,
} from "@/core/runtime/adapter";
import { RuntimeStatusBadge } from "../RuntimeStatusBadge";

function makeAdapter(initial: AdapterState): RuntimeAdapter {
  return {
    kind: "remote",
    label: "Kernel",
    capabilities: {
      canHealthCheck: true,
      canShutdown: true,
      canRestart: true,
      supportsLsp: true,
    },
    state: atom<AdapterState>(initial),
  };
}

let store: ReturnType<typeof createStore>;

const wrapper = ({ children }: { children: ReactNode }) => (
  <Provider store={store}>
    <TooltipProvider>{children}</TooltipProvider>
  </Provider>
);

beforeEach(() => {
  vi.useFakeTimers();
  store = createStore();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("RuntimeStatusBadge — footer surface", () => {
  it("hides itself when state.kind=ready (showWhen=active, default)", () => {
    store.set(runtimeAdapterAtom, makeAdapter({ kind: "ready" }));
    const { container } = render(<RuntimeStatusBadge surface="footer" />, {
      wrapper,
    });
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a healthy pill with showWhen=always", () => {
    store.set(runtimeAdapterAtom, makeAdapter({ kind: "ready" }));
    render(<RuntimeStatusBadge surface="footer" showWhen="always" />, {
      wrapper,
    });
    expect(screen.getByTestId("runtime-status-footer")).toBeInTheDocument();
    expect(screen.getByText("Kernel")).toBeInTheDocument();
  });

  it("shows a spinner while connecting", () => {
    store.set(
      runtimeAdapterAtom,
      makeAdapter({
        kind: "connecting",
        progress: { label: "Loading Pyodide…" },
      }),
    );
    render(<RuntimeStatusBadge surface="footer" />, { wrapper });
    expect(screen.getByTestId("runtime-status-footer")).toBeInTheDocument();
  });

  it("shows the failure icon on state.kind=failed", () => {
    store.set(
      runtimeAdapterAtom,
      makeAdapter({
        kind: "failed",
        error: { message: "Boom", errorKind: "init" },
      }),
    );
    render(<RuntimeStatusBadge surface="footer" />, { wrapper });
    expect(screen.getByTestId("runtime-status-footer")).toBeInTheDocument();
  });
});

describe("RuntimeStatusBadge — header surface", () => {
  it("renders nothing when ready", () => {
    store.set(runtimeAdapterAtom, makeAdapter({ kind: "ready" }));
    const { container } = render(
      <RuntimeStatusBadge surface="header" showWhen="always" />,
      { wrapper },
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the ellipsis indicator while connecting", () => {
    store.set(
      runtimeAdapterAtom,
      makeAdapter({ kind: "connecting", progress: { label: "…" } }),
    );
    render(<RuntimeStatusBadge surface="header" />, { wrapper });
    expect(screen.getByTestId("runtime-status-header")).toBeInTheDocument();
  });
});

describe("RuntimeStatusBadge — alert surface", () => {
  it("delays rendering by delayMs (defaults to 1000)", () => {
    store.set(
      runtimeAdapterAtom,
      makeAdapter({ kind: "connecting", progress: { label: "…" } }),
    );
    render(<RuntimeStatusBadge surface="alert" />, { wrapper });
    expect(
      screen.queryByTestId("runtime-status-alert"),
    ).not.toBeInTheDocument();

    act(() => vi.advanceTimersByTime(1000));
    expect(screen.getByTestId("runtime-status-alert")).toBeInTheDocument();
  });

  it("respects an explicit delayMs override", () => {
    store.set(
      runtimeAdapterAtom,
      makeAdapter({ kind: "connecting", progress: { label: "…" } }),
    );
    render(<RuntimeStatusBadge surface="alert" delayMs={0} />, { wrapper });
    act(() => vi.advanceTimersByTime(0));
    expect(screen.getByTestId("runtime-status-alert")).toBeInTheDocument();
  });

  it("renders nothing when ready", () => {
    store.set(runtimeAdapterAtom, makeAdapter({ kind: "ready" }));
    const { container } = render(
      <RuntimeStatusBadge surface="alert" showWhen="always" />,
      { wrapper },
    );
    expect(container).toBeEmptyDOMElement();
  });
});
