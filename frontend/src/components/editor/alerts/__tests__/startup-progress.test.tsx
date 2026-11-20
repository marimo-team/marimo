/* Copyright 2026 Marimo. All rights reserved. */
import { act, fireEvent, render, screen } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { expect, it } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { EnvironmentOperation } from "@/core/alerts/environment";
import { alertAtom } from "@/core/alerts/state";
import { startupProgressAtom } from "@/core/network/connection";
import type { DisplayConnectionNotice } from "@/core/network/useConnectionNotice";
import { StartupOutput } from "../startup-output";
import { StartupProgress } from "../startup-progress";

const notice: DisplayConnectionNotice = {
  kind: "startup",
  phase: "starting-kernel",
  sandbox: true,
  title: "Starting kernel",
  description: "Connecting to this notebook.",
  pending: true,
  ready: false,
  error: null,
};

const preparation: EnvironmentOperation = {
  operation_id: "prepare-1",
  action: "prepare",
  source: "kernel",
  status: { kind: "succeeded" },
  packages: {},
  logs: {
    environment:
      "Using Python\nResolving dependencies\nDownloading numpy\nInstalled 24 packages\n",
  },
};

function restorePreparation(
  store: ReturnType<typeof createStore>,
  operation: EnvironmentOperation,
) {
  store.set(alertAtom, (state) => ({
    ...state,
    environments: {
      ...state.environments,
      kernel: { restart_required: false, operations: [operation] },
    },
  }));
}

it("restores separate compact previews and keeps expanded output open through snapshots and live updates", () => {
  const store = createStore();
  restorePreparation(store, preparation);
  store.set(startupProgressAtom, {
    phase: "starting-kernel",
    logs: "Using Python\nLoading runtime\nLaunching kernel\nConnecting\n",
    log_mode: "replace",
  });
  render(
    <Provider store={store}>
      <StartupProgress notice={notice} surface="sidebar" />
    </Provider>,
    { wrapper: TooltipProvider },
  );
  const prepareButton = screen.getByRole("button", {
    name: "Expand environment preparation output",
  });
  expect(prepareButton).toHaveTextContent("Installed 24 packages");
  expect(prepareButton).toHaveTextContent("Resolving dependencies");
  expect(prepareButton).toHaveTextContent("Downloading numpy");
  expect(prepareButton).not.toHaveTextContent("Using Python");
  const kernelButton = screen.getByRole("button", {
    name: "Expand kernel startup output",
  });
  expect(kernelButton).toHaveAttribute("aria-expanded", "false");
  expect(kernelButton).toHaveTextContent(
    "Loading runtimeLaunching kernelConnecting",
  );
  expect(kernelButton).not.toHaveTextContent("Using Python");

  fireEvent.click(prepareButton);
  const prepareOutput = screen.getByLabelText("environment preparation output");
  expect(prepareOutput).toBeVisible();
  expect(prepareOutput.textContent).toBe(preparation.logs.environment);
  act(() => restorePreparation(store, { ...preparation }));
  expect(prepareOutput).toBeVisible();

  fireEvent.click(kernelButton);
  act(() =>
    store.set(startupProgressAtom, {
      phase: "starting-kernel",
      logs: "Kernel connected\n",
      log_mode: "append",
    }),
  );
  const output = screen.getByLabelText("kernel startup output");
  expect(output).toBeVisible();
  expect(output.textContent).toBe(
    "Using Python\nLoading runtime\nLaunching kernel\nConnecting\nKernel connected\n",
  );
  expect(prepareOutput.textContent).toBe(preparation.logs.environment);
});

it("starts a new preparation compact and offers no disclosure before output arrives", () => {
  const store = createStore();
  const { rerender } = render(
    <Provider store={store}>
      <StartupProgress
        notice={{ ...notice, phase: "preparing-environment" }}
        surface="sidebar"
      />
    </Provider>,
    { wrapper: TooltipProvider },
  );
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
  act(() => restorePreparation(store, preparation));
  fireEvent.click(screen.getByRole("button", { name: /Expand environment/ }));
  act(() =>
    restorePreparation(store, {
      ...preparation,
      operation_id: "prepare-2",
      status: { kind: "running" },
      logs: { environment: "Trying again\n" },
    }),
  );
  expect(
    screen.getByRole("button", { name: /Expand environment/ }),
  ).toHaveTextContent("Trying again");
  expect(
    screen.getByLabelText("environment preparation output"),
  ).not.toBeVisible();

  rerender(
    <Provider store={store}>
      <StartupProgress notice={notice} surface="notebook" />
    </Provider>,
  );
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

it("preserves reading position and selected text while output streams, then resumes following", () => {
  const logs = "Resolving dependencies\nDownloading numpy\n";
  const { rerender } = render(
    <StartupOutput logs={logs} label="preparation output" />,
    { wrapper: TooltipProvider },
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Expand preparation output" }),
  );
  const output = screen.getByLabelText("preparation output");
  Object.defineProperties(output, {
    scrollHeight: { value: 1000 },
    clientHeight: { value: 200 },
  });
  fireEvent.scroll(output, { target: { scrollTop: 100 } });
  expect(screen.getByRole("button", { name: "Jump to latest" })).toBeVisible();

  const selection = document.getSelection();
  const range = document.createRange();
  range.selectNodeContents(output);
  act(() => {
    selection?.removeAllRanges();
    selection?.addRange(range);
    document.dispatchEvent(new Event("selectionchange"));
  });
  rerender(
    <StartupOutput
      logs={`${logs}Downloaded numpy\n`}
      label="preparation output"
    />,
  );
  expect(selection?.toString()).toBe(logs);
  expect(output.scrollTop).toBe(100);
  expect(output.textContent).toBe(`${logs}Downloaded numpy\n`);

  fireEvent.click(screen.getByRole("button", { name: "Jump to latest" }));
  expect(selection?.isCollapsed).toBe(true);
  expect(output.scrollTop).toBeGreaterThan(100);
  expect(
    screen.queryByRole("button", { name: "Jump to latest" }),
  ).not.toBeInTheDocument();

  fireEvent.click(
    screen.getByRole("button", { name: "Collapse preparation output" }),
  );
  expect(output).not.toBeVisible();
});
