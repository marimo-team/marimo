/* Copyright 2026 Marimo. All rights reserved. */

import { render, screen } from "@testing-library/react";
import { atom, createStore, Provider } from "jotai";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it } from "vitest";
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
  store = createStore();
});

describe("RuntimeStatusBadge", () => {
  it("hides itself when the runtime is ready", () => {
    store.set(runtimeAdapterAtom, makeAdapter({ kind: "ready" }));
    const { container } = render(<RuntimeStatusBadge />, { wrapper });
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a labeled spinner pill while connecting", () => {
    store.set(
      runtimeAdapterAtom,
      makeAdapter({
        kind: "connecting",
        progress: { label: "Loading Pyodide…" },
      }),
    );
    render(<RuntimeStatusBadge />, { wrapper });
    expect(screen.getByTestId("runtime-status-footer")).toBeInTheDocument();
    expect(screen.getByText("Kernel")).toBeInTheDocument();
  });

  it("shows the failure icon when the runtime fails", () => {
    store.set(
      runtimeAdapterAtom,
      makeAdapter({
        kind: "failed",
        error: { message: "Boom", errorKind: "init" },
      }),
    );
    render(<RuntimeStatusBadge />, { wrapper });
    expect(screen.getByTestId("runtime-status-footer")).toBeInTheDocument();
  });
});
