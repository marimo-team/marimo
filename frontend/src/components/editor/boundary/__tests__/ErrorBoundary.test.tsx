/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { PropsWithChildren, ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { ModalProvider } from "@/components/modal/ImperativeModal";
import { TooltipProvider } from "@/components/ui/tooltip";
import { initialNotebookState, notebookAtom } from "@/core/cells/cells";
import { viewStateAtom } from "@/core/mode";
import { connectionAtom } from "@/core/network/connection";
import { requestClientAtom } from "@/core/network/requests";
import type { EnvironmentInfo } from "@/core/network/types";
import { filenameAtom } from "@/core/saving/file-state";
import { store } from "@/core/state/jotai";
import { WebSocketState } from "@/core/websocket/types";
import { ErrorBoundary } from "../ErrorBoundary";

vi.mock("@/utils/copy", () => ({
  copyToClipboard: vi.fn().mockResolvedValue(undefined),
}));

const environment: EnvironmentInfo = {
  marimo: "1.2.3",
  editable: false,
  location: "~/.venv/site-packages/marimo",
  OS: "Darwin",
  "OS Version": "25.0",
  Processor: "arm",
  "Python Version": "3.12.9",
  Locale: "en_US",
  Binaries: { Browser: "chrome 140", Node: "v22", uv: "0.11" },
  Dependencies: { click: "8.4.2" },
  "Optional Dependencies": { pandas: "3.0.0" },
  "Experimental Flags": {},
};

const CRASH_MESSAGE = "cell output crashed";

function CrashingChild(): never {
  throw new Error(CRASH_MESSAGE);
}

function RecoverableChild({ crash }: { crash: boolean }) {
  if (crash) {
    throw new Error(CRASH_MESSAGE);
  }
  return <p>recovered child</p>;
}

function DescendantProviders({ children }: PropsWithChildren) {
  return (
    <TooltipProvider>
      <ModalProvider>{children}</ModalProvider>
    </TooltipProvider>
  );
}

function isExpectedReactExceptionOutput(args: unknown[]): boolean {
  return args.some((arg) => {
    if (arg instanceof Error) {
      return arg.message.includes(CRASH_MESSAGE);
    }
    return (
      typeof arg === "string" &&
      (arg.includes(CRASH_MESSAGE) ||
        arg.includes("The above error occurred") ||
        arg.includes("React will try to recreate this component tree"))
    );
  });
}

function suppressExpectedReactException() {
  return vi.spyOn(console, "error").mockImplementation((...args) => {
    if (isExpectedReactExceptionOutput(args)) {
      return;
    }
    throw new Error(`Unexpected console.error: ${args.map(String).join(" ")}`);
  });
}

let consoleError: ReturnType<typeof vi.spyOn> | undefined;

function renderCrashedBoundary(child: ReactNode = <CrashingChild />) {
  consoleError?.mockRestore();
  consoleError = suppressExpectedReactException();
  return render(<ErrorBoundary>{child}</ErrorBoundary>);
}

function setRequestClient(
  overrides?: Parameters<typeof MockRequestClient.create>[0],
) {
  const client = MockRequestClient.create(overrides);
  store.set(requestClientAtom, client);
  return client;
}

async function openReportDialog() {
  const trigger = screen.getByRole("button", { name: "Report an issue" });
  trigger.focus();
  fireEvent.click(trigger);
  return screen.findByRole("dialog");
}

async function expectReportButtonFocused() {
  await waitFor(() => {
    expect(
      screen.getByRole("button", { name: "Report an issue" }),
    ).toHaveFocus();
  });
}

async function closeReportDialog(method: "escape" | "close") {
  const dialog = await screen.findByRole("dialog");
  if (method === "escape") {
    fireEvent.keyDown(dialog, { key: "Escape" });
  } else {
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
  }
  await waitFor(() => {
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
  await expectReportButtonFocused();
}

async function expectRealReportModal() {
  const dialog = await openReportDialog();
  expect(dialog).toHaveTextContent("Report an issue");
  expect(screen.getByRole("link", { name: "Open GitHub issue" })).toBeVisible();
  expect(
    screen.getByRole("checkbox", { name: "Include errors" }),
  ).toBeVisible();
  expect(
    screen.getByRole("checkbox", { name: "Include notebook code" }),
  ).toBeVisible();
  await screen.findByText("Environment details");
  return dialog;
}

function resetSharedState() {
  localStorage.clear();
  store.set(requestClientAtom, null);
  store.set(notebookAtom, initialNotebookState());
  store.set(viewStateAtom, { mode: "edit", cellAnchor: null });
  store.set(connectionAtom, { state: WebSocketState.OPEN });
  store.set(filenameAtom, "/project/example.py");
}

describe("ErrorBoundary report dialog", () => {
  beforeEach(() => {
    resetSharedState();
  });

  afterEach(() => {
    consoleError?.mockRestore();
    consoleError = undefined;
    resetSharedState();
  });

  it("opens the report modal after a child render exception", async () => {
    const { getEnvironmentInfo } = setRequestClient({
      getEnvironmentInfo: vi.fn().mockResolvedValue(environment),
    });

    renderCrashedBoundary();

    expect(screen.getByText("Something went wrong")).toBeVisible();
    expect(screen.getByText("cell output crashed")).toBeVisible();
    expect(screen.getByTestId("reset-error-boundary-button")).toBeVisible();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(getEnvironmentInfo).not.toHaveBeenCalled();

    await expectRealReportModal();
    await waitFor(() => expect(getEnvironmentInfo).toHaveBeenCalledOnce());
  });

  it("still opens one report dialog after descendant providers disappear", async () => {
    const { getEnvironmentInfo } = setRequestClient({
      getEnvironmentInfo: vi.fn().mockResolvedValue(environment),
    });

    renderCrashedBoundary(
      <DescendantProviders>
        <CrashingChild />
      </DescendantProviders>,
    );

    await expectRealReportModal();
    expect(screen.getAllByRole("dialog")).toHaveLength(1);
    await waitFor(() => expect(getEnvironmentInfo).toHaveBeenCalledOnce());
  });

  it("shows partial diagnostics when the request client is missing", async () => {
    renderCrashedBoundary();

    await openReportDialog();
    await screen.findByText("Environment details");

    expect(
      screen.getByText("Server environment information unavailable"),
    ).toBeVisible();
    expect(
      screen.queryByText("Loading environment details…"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Retry" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("checkbox", { name: "Include notebook code" }),
    ).toBeDisabled();
    expect(screen.getByText("Notebook source is unavailable.")).toBeVisible();
    const link = screen.getByRole("link", { name: "Open GitHub issue" });
    expect(link.getAttribute("href") ?? "").toContain("&env=");
  });

  it("does not request environment or source while the report dialog is closed", async () => {
    localStorage.setItem(
      "marimo:issue-report:include-code",
      JSON.stringify(true),
    );
    const { getEnvironmentInfo, readCode } = setRequestClient({
      getEnvironmentInfo: vi.fn().mockResolvedValue(environment),
      readCode: vi.fn().mockResolvedValue({ contents: "import marimo" }),
    });

    renderCrashedBoundary();

    expect(screen.getByText("Something went wrong")).toBeVisible();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(getEnvironmentInfo).not.toHaveBeenCalled();
    expect(readCode).not.toHaveBeenCalled();
  });

  it("restores focus to the report button after closing with Escape", async () => {
    setRequestClient({
      getEnvironmentInfo: vi.fn().mockResolvedValue(environment),
    });
    renderCrashedBoundary();
    await openReportDialog();
    await closeReportDialog("escape");
    expect(screen.getByText(CRASH_MESSAGE)).toBeVisible();
  });

  it("restores focus to the report button after closing with the close control", async () => {
    setRequestClient({
      getEnvironmentInfo: vi.fn().mockResolvedValue(environment),
    });
    renderCrashedBoundary();
    await openReportDialog();
    await closeReportDialog("close");
    expect(screen.getByText(CRASH_MESSAGE)).toBeVisible();
  });

  it("reopens the report dialog while the original error remains", async () => {
    setRequestClient({
      getEnvironmentInfo: vi.fn().mockResolvedValue(environment),
    });
    renderCrashedBoundary();
    await openReportDialog();
    await closeReportDialog("escape");
    expect(screen.getByText(CRASH_MESSAGE)).toBeVisible();
    await expectRealReportModal();
    expect(screen.getByText(CRASH_MESSAGE)).toBeVisible();
  });

  it("restores the child after try again once the failure is cleared", () => {
    setRequestClient({
      getEnvironmentInfo: vi.fn().mockResolvedValue(environment),
    });
    const view = renderCrashedBoundary(<RecoverableChild crash={true} />);
    expect(screen.getByText("Something went wrong")).toBeVisible();

    view.rerender(
      <ErrorBoundary>
        <RecoverableChild crash={false} />
      </ErrorBoundary>,
    );
    fireEvent.click(screen.getByTestId("reset-error-boundary-button"));

    expect(screen.getByText("recovered child")).toBeVisible();
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
  });

  it("does not read notebook source when opened with fresh inclusion preferences", async () => {
    const { readCode } = setRequestClient({
      getEnvironmentInfo: vi.fn().mockResolvedValue(environment),
      readCode: vi.fn().mockResolvedValue({ contents: "import marimo" }),
    });

    renderCrashedBoundary();
    await expectRealReportModal();

    expect(readCode).not.toHaveBeenCalled();
  });
});
