/* Copyright 2026 Marimo. All rights reserved. */
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import type { EnvironmentOperation } from "@/core/alerts/environment";
import { alertAtom, getPackageAlert } from "@/core/alerts/state";
import { notebookAtom } from "@/core/cells/cells";
import { CellId } from "@/core/cells/ids";
import { AppConfigSchema } from "@/core/config/config-schema";
import { connectionAtom } from "@/core/network/connection";
import { sandboxAtom, sandboxSyncAtom } from "@/core/packages/sandbox-state";
import { WebSocketClosedReason, WebSocketState } from "@/core/websocket/types";
import { chromeAtom } from "../../chrome/state";
import { ConnectionNotice } from "../connection-notice";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

function mount(existingCells = false) {
  const store = createStore();
  store.set(sandboxAtom, {
    backend: "pixi",
    manifest: "",
    filename: "notebook.py",
  });
  store.set(connectionAtom, {
    state: WebSocketState.CONNECTING,
    phase: "preparing-environment",
  });
  if (existingCells) {
    store.set(
      notebookAtom,
      MockNotebook.notebookState({
        cellData: { [CellId.create()]: { code: "1 + 1" } },
      }),
    );
  }
  render(
    <Provider store={store}>
      <ConnectionNotice
        appConfig={AppConfigSchema.parse({})}
        onRetry={vi.fn()}
      />
    </Provider>,
  );
  return store;
}

it("shows both stages in an empty notebook, checks them off, then dismisses Ready", () => {
  const store = mount();
  act(() => vi.advanceTimersByTime(500));
  const steps = within(
    screen.getByRole("list", { name: "Notebook startup stages" }),
  );
  expect(steps.getByText("Preparing environment")).toBeInTheDocument();
  expect(steps.getByText("Start kernel")).toBeInTheDocument();
  act(() =>
    store.set(connectionAtom, {
      state: WebSocketState.CONNECTING,
      phase: "starting-kernel",
    }),
  );
  expect(steps.getByText("Environment ready")).toBeInTheDocument();
  expect(steps.getByText("Starting kernel")).toBeInTheDocument();
  act(() => store.set(connectionAtom, { state: WebSocketState.OPEN }));
  expect(
    screen.getByRole("heading", { name: "Your notebook is ready" }),
  ).toBeInTheDocument();
  expect(steps.getByText("Kernel ready")).toBeInTheDocument();
  act(() => vi.advanceTimersByTime(1000));
  expect(screen.getByRole("status")).toHaveTextContent(
    "Your notebook is ready",
  );
  act(() => vi.advanceTimersByTime(1000));
  expect(
    screen.queryByRole("region", { name: "Notebook startup" }),
  ).not.toBeInTheDocument();
});

it("opens Packages from the minimal inline status when cells exist", () => {
  const store = mount(true);
  act(() => vi.advanceTimersByTime(500));
  expect(screen.queryByRole("list")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Open Packages/ }));
  expect(store.get(chromeAtom)).toMatchObject({
    isSidebarOpen: true,
    selectedPanel: "packages",
  });
  act(() => store.set(connectionAtom, { state: WebSocketState.OPEN }));
  expect(screen.getByRole("status")).toHaveTextContent(/^Ready$/);
});

it("does not flash Ready for a startup that finished before the notice appeared", () => {
  const store = mount(true);
  act(() => vi.advanceTimersByTime(200));
  act(() => store.set(connectionAtom, { state: WebSocketState.OPEN }));
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  act(() => vi.advanceTimersByTime(2000));
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

it("replaces Ready with a new attempt and never dismisses a failure", () => {
  const store = mount();
  act(() => vi.advanceTimersByTime(500));
  act(() => store.set(connectionAtom, { state: WebSocketState.OPEN }));
  act(() => vi.advanceTimersByTime(1000));
  act(() =>
    store.set(connectionAtom, {
      state: WebSocketState.CONNECTING,
      phase: "starting-kernel",
    }),
  );
  act(() => vi.advanceTimersByTime(500));
  expect(screen.getByText("Starting kernel")).toBeInTheDocument();
  act(() =>
    store.set(connectionAtom, {
      state: WebSocketState.CLOSED,
      code: WebSocketClosedReason.KERNEL_STARTUP_ERROR,
      phase: "starting-kernel",
      reason: "Kernel startup failed",
    }),
  );
  act(() => vi.advanceTimersByTime(10_000));
  expect(screen.getByRole("status")).toHaveTextContent(
    "Kernel failed to start",
  );
});

it("shows a sync as a single operation, without pretending to restart the kernel", () => {
  const store = mount(true);
  act(() => {
    store.set(connectionAtom, { state: WebSocketState.OPEN });
    store.set(sandboxSyncAtom, { pending: true, error: null });
  });
  act(() => vi.advanceTimersByTime(500));
  expect(screen.getByRole("status")).toHaveTextContent("Syncing sandbox");
  expect(screen.queryByRole("list")).not.toBeInTheDocument();
  act(() => store.set(sandboxSyncAtom, { pending: false, error: null }));
  expect(screen.getByRole("status")).toHaveTextContent("Environment synced");
});

it("restores syncing in the existing status and stays quiet for a completed snapshot", () => {
  const store = mount(true);
  const operation: EnvironmentOperation = {
    operation_id: "sync",
    action: "sync",
    source: "kernel",
    status: { kind: "succeeded" },
    packages: {},
    logs: { environment: "Sync complete\n" },
  };
  const restore = (status: EnvironmentOperation["status"]) =>
    store.set(alertAtom, (value) => ({
      ...value,
      environments: {
        ...value.environments,
        kernel: {
          restart_required: false,
          operations: [{ ...operation, status }],
        },
      },
    }));
  act(() => {
    store.set(connectionAtom, { state: WebSocketState.OPEN });
    restore({ kind: "succeeded" });
  });
  act(() => vi.advanceTimersByTime(2000));
  expect(screen.queryByRole("status")).not.toBeInTheDocument();

  act(() => restore({ kind: "running" }));
  act(() => vi.advanceTimersByTime(500));
  expect(screen.getByRole("status")).toHaveTextContent("Syncing sandbox");
  expect(getPackageAlert(store.get(alertAtom))).toBeNull();
  for (const [status, error] of [
    [{ kind: "failed", error: "Dependency conflict" }, "Dependency conflict"],
    [
      { kind: "restart-required", reason: "Restart the kernel" },
      "Restart the kernel",
    ],
    [{ kind: "cancelled" }, "Sandbox sync was interrupted."],
  ] as const) {
    act(() => restore(status));
    expect(screen.getByRole("status")).toHaveTextContent("Sandbox sync failed");
    expect(store.get(sandboxSyncAtom)).toEqual({ pending: false, error });
  }
});
