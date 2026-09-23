/* Copyright 2026 Marimo. All rights reserved. */
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { TooltipProvider } from "@/components/ui/tooltip";
import { alertAtom } from "@/core/alerts/state";
import type { EnvironmentOperation } from "@/core/alerts/environment";
import { kernelStartupErrorAtom } from "@/core/errors/state";
import { connectionAtom, startupProgressAtom } from "@/core/network/connection";
import { requestClientAtom } from "@/core/network/requests";
import { sandboxAtom, sandboxSyncAtom } from "@/core/packages/sandbox-state";
import { WebSocketClosedReason, WebSocketState } from "@/core/websocket/types";
import PackagesPanel from "../packages-panel";
import { PanelSectionProvider } from "../panel-context";
import { SandboxToggle } from "../sandbox-toggle";

const preparation: EnvironmentOperation = {
  operation_id: "prepare-1",
  action: "prepare",
  source: "kernel",
  status: { kind: "succeeded" },
  packages: {},
  logs: {
    environment:
      "Using Python\nResolved dependencies\nDownloaded numpy\nInstalled numpy\n",
  },
};

function mount({
  preparing = false,
  backend = "uv",
}: { preparing?: boolean; backend?: "uv" | "pixi" | null } = {}) {
  const store = createStore();
  store.set(sandboxAtom, {
    backend,
    manifest: "dependencies = []",
    filename: "notebook.py",
  });
  store.set(
    connectionAtom,
    preparing
      ? { state: WebSocketState.CONNECTING, phase: "preparing-environment" }
      : { state: WebSocketState.OPEN },
  );
  store.set(alertAtom, (state) => ({
    ...state,
    environments: {
      ...state.environments,
      kernel: {
        restart_required: false,
        operations: backend ? [preparation] : [],
      },
    },
  }));
  if (backend) {
    store.set(startupProgressAtom, {
      phase: preparing ? "preparing-environment" : "starting-kernel",
      logs: preparing
        ? ""
        : "Loading runtime\nLaunching kernel\nKernel connected\n",
      log_mode: "replace",
    });
  }
  const client = MockRequestClient.create({
    getDependencyTree: vi.fn(async () => ({
      context: backend
        ? { kind: "sandbox" as const, backend }
        : { kind: "package-manager" as const, name: "pip" },
      tree: {
        name: "<root>",
        version: null,
        tags: [],
        dependencies: [
          { name: "numpy", version: "2.0.0", tags: [], dependencies: [] },
        ],
      },
    })),
    getPackageList: vi.fn(async () => ({
      packages: [{ name: "numpy", version: "2.0.0" }],
    })),
  });
  store.set(requestClientAtom, client);
  render(
    <Provider store={store}>
      <TooltipProvider>
        <SandboxToggle section="sidebar" />
        <PanelSectionProvider value="sidebar">
          <PackagesPanel />
        </PanelSectionProvider>
      </TooltipProvider>
    </Provider>,
  );
  return { store, client };
}

it("opens restored preparation and kernel logs without reopening completed startup on refresh", async () => {
  mount();
  await screen.findByText("numpy");
  const toggle = screen.getByRole("button", { name: "uv sandbox" });
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  expect(
    screen.queryByRole("region", { name: "Sandbox details" }),
  ).not.toBeInTheDocument();
  fireEvent.click(toggle);
  const details = within(
    screen.getByRole("region", { name: "Sandbox details" }),
  );
  expect(details.getByText("Environment prepared")).toBeVisible();
  expect(details.getByText("Kernel started")).toBeVisible();
  fireEvent.click(
    details.getByRole("button", {
      name: "Expand environment preparation output",
    }),
  );
  fireEvent.click(
    details.getByRole("button", { name: "Expand kernel startup output" }),
  );
  expect(
    details.getByLabelText("environment preparation output").textContent,
  ).toBe(preparation.logs.environment);
  expect(details.getByLabelText("kernel startup output")).toHaveTextContent(
    "Loading runtime",
  );
  fireEvent.click(toggle);
  fireEvent.click(toggle);
  expect(
    details.getByLabelText("environment preparation output"),
  ).toBeVisible();
  expect(details.getByLabelText("kernel startup output")).toBeVisible();
});

it.each([false, true])(
  "retains the progression after completion with inspecting=%s",
  async (inspecting) => {
    const { store, client } = mount({ preparing: true });
    const toggle = screen.getByRole("button", { name: "uv sandbox" });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(client.getDependencyTree).not.toHaveBeenCalled();
    if (inspecting) {
      const preview = screen.getByRole("button", {
        name: "Expand environment preparation output",
      });
      fireEvent.pointerDown(preview);
      fireEvent.click(preview);
    }
    act(() => {
      store.set(startupProgressAtom, {
        phase: "starting-kernel",
        logs: "Launching kernel\n",
        log_mode: "replace",
      });
      store.set(connectionAtom, {
        state: WebSocketState.CONNECTING,
        phase: "starting-kernel",
      });
    });
    act(() => store.set(connectionAtom, { state: WebSocketState.OPEN }));
    await screen.findByText("numpy");
    expect(toggle).toHaveAttribute("aria-expanded", String(inspecting));
    if (!inspecting) {
      fireEvent.click(toggle);
    }
    expect(screen.getByText("Environment prepared")).toBeVisible();
    expect(screen.getByText("Kernel started")).toBeVisible();
    expect(
      screen.getByLabelText("environment preparation output"),
    ).toHaveProperty("hidden", !inspecting);
    expect(
      screen.getByRole("button", { name: "Expand kernel startup output" }),
    ).toHaveTextContent("Launching kernel");
  },
);

it("opens a startup error even after collapsing preparation and keeps both step outputs available", () => {
  const { store } = mount({ preparing: true, backend: "pixi" });
  const toggle = screen.getByRole("button", { name: "pixi sandbox" });
  fireEvent.click(toggle);
  act(() => {
    store.set(startupProgressAtom, {
      phase: "starting-kernel",
      logs: "Loading runtime\nImport failed\n",
      log_mode: "replace",
    });
    store.set(kernelStartupErrorAtom, "Could not import the runtime");
    store.set(connectionAtom, {
      state: WebSocketState.CLOSED,
      phase: "starting-kernel",
      code: WebSocketClosedReason.KERNEL_STARTUP_ERROR,
      reason: "Kernel startup failed",
    });
  });
  expect(toggle).toHaveAttribute("aria-expanded", "true");
  expect(within(toggle).getByRole("status")).toHaveAccessibleName(
    "Kernel failed to start",
  );
  expect(screen.getByLabelText("Error details")).toHaveTextContent(
    "Could not import the runtime",
  );
  expect(screen.getByText("Environment prepared")).toBeVisible();
  expect(
    screen.getByRole("button", {
      name: "Expand environment preparation output",
    }),
  ).toHaveTextContent("Installed numpy");
  expect(
    screen.getByRole("button", { name: "Expand kernel startup output" }),
  ).toHaveTextContent("Import failed");
  fireEvent.click(toggle);
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  fireEvent.click(toggle);
  expect(screen.getByLabelText("Error details")).toBeVisible();
});

it("keeps packages usable when a sync fails and exposes recovery in the details", async () => {
  const { store } = mount();
  await screen.findByText("numpy");
  const toggle = screen.getByRole("button", { name: "uv sandbox" });
  act(() => store.set(sandboxSyncAtom, { pending: true, error: null }));
  expect(within(toggle).getByRole("status")).toHaveAccessibleName(
    "Syncing sandbox…",
  );
  fireEvent.click(toggle);
  act(() =>
    store.set(sandboxSyncAtom, { pending: false, error: "No solution" }),
  );
  expect(toggle).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByLabelText("Error details")).toHaveTextContent(
    "No solution",
  );
  expect(screen.getByText("numpy")).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Retry sync" }),
  ).toBeInTheDocument();
});

it("does not add a toggle or startup details to an existing environment", async () => {
  mount({ backend: null });
  await screen.findByText("numpy");
  expect(
    screen.queryByRole("button", { name: /sandbox/ }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("region", { name: "Sandbox details" }),
  ).not.toBeInTheDocument();
});
