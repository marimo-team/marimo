/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Provider } from "jotai";
import type React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { Dialog } from "@/components/ui/dialog";
import { Constants } from "@/core/constants";
import { TooltipProvider } from "@/components/ui/tooltip";
import { viewStateAtom } from "@/core/mode";
import { connectionAtom } from "@/core/network/connection";
import { requestClientAtom } from "@/core/network/requests";
import type { EnvironmentInfo } from "@/core/network/types";
import { filenameAtom } from "@/core/saving/file-state";
import { store } from "@/core/state/jotai";
import { WebSocketState } from "@/core/websocket/types";
import * as copyModule from "@/utils/copy";
import { FeedbackModal } from "../feedback-button";

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

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <Provider store={store}>
      <TooltipProvider>
        <Dialog open={true}>{children}</Dialog>
      </TooltipProvider>
    </Provider>
  );
}

describe("FeedbackModal issue reporting", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    store.set(requestClientAtom, MockRequestClient.create());
    store.set(viewStateAtom, { mode: "edit", cellAnchor: null });
    store.set(connectionAtom, { state: WebSocketState.OPEN });
    store.set(filenameAtom, "/project/example.py");
  });

  it("loads and previews issue environment details", async () => {
    store.set(
      requestClientAtom,
      MockRequestClient.create({
        getEnvironmentInfo: vi.fn().mockResolvedValue(environment),
      }),
    );
    render(<FeedbackModal onClose={vi.fn()} />, { wrapper });

    expect(screen.getByText("Loading environment details…")).toBeVisible();
    await screen.findByText("Environment details");
    expect(screen.getByText(/"marimo": "1.2.3"/)).toBeInTheDocument();
  });

  it("toggles the environment preview between show more and show less", async () => {
    store.set(
      requestClientAtom,
      MockRequestClient.create({
        getEnvironmentInfo: vi.fn().mockResolvedValue(environment),
      }),
    );
    render(<FeedbackModal onClose={vi.fn()} />, { wrapper });
    await screen.findByText("Environment details");

    const toggle = screen.getByRole("button", { name: "Show more" });
    fireEvent.click(toggle);
    expect(
      screen.getByRole("button", { name: "Show less" }),
    ).toBeInTheDocument();
  });

  it("copies partial environment JSON when the environment request fails", async () => {
    store.set(
      requestClientAtom,
      MockRequestClient.create({
        getEnvironmentInfo: vi.fn().mockRejectedValue(new Error("offline")),
      }),
    );
    render(<FeedbackModal onClose={vi.fn()} />, { wrapper });

    await screen.findByText("Server environment information unavailable");
    fireEvent.click(
      screen.getByRole("button", { name: "Copy environment JSON" }),
    );
    await waitFor(() =>
      expect(copyModule.copyToClipboard).toHaveBeenCalledWith(
        expect.stringContaining("Environment Collection Error"),
      ),
    );
  });

  it("copies raw environment JSON", async () => {
    store.set(
      requestClientAtom,
      MockRequestClient.create({
        getEnvironmentInfo: vi.fn().mockResolvedValue(environment),
      }),
    );
    render(<FeedbackModal onClose={vi.fn()} />, { wrapper });
    await screen.findByText("Environment details");

    fireEvent.click(
      screen.getByRole("button", { name: "Copy environment JSON" }),
    );
    await waitFor(() =>
      expect(copyModule.copyToClipboard).toHaveBeenCalledWith(
        expect.stringContaining('"marimo": "1.2.3"'),
      ),
    );
  });

  it("prefills the notebook code after checking include code", async () => {
    const readCode = vi.fn().mockResolvedValue({ contents: "import marimo" });
    store.set(
      requestClientAtom,
      MockRequestClient.create({
        getEnvironmentInfo: vi.fn().mockResolvedValue(environment),
        readCode,
      }),
    );
    render(<FeedbackModal onClose={vi.fn()} />, { wrapper });
    const link = screen.getByRole("link", { name: "Open GitHub issue" });
    await screen.findByText("Environment details");

    expect(readCode).not.toHaveBeenCalled();
    expect(link.getAttribute("href") ?? "").not.toContain("reproduction-code=");

    fireEvent.click(
      screen.getByRole("checkbox", { name: "Include notebook code" }),
    );
    await waitFor(() => expect(readCode).toHaveBeenCalledOnce());
    await waitFor(() => {
      const href = link.getAttribute("href") ?? "";
      expect(href).toContain("reproduction-code=");
      expect(href).toContain(encodeURIComponent("import marimo"));
    });
  });

  it("disables include code and explains why when disconnected", async () => {
    store.set(connectionAtom, { state: WebSocketState.CONNECTING });
    store.set(
      requestClientAtom,
      MockRequestClient.create({
        getEnvironmentInfo: vi.fn().mockResolvedValue(environment),
      }),
    );
    render(<FeedbackModal onClose={vi.fn()} />, { wrapper });
    await screen.findByText("Environment details");

    expect(
      screen.getByRole("checkbox", { name: "Include notebook code" }),
    ).toBeDisabled();
    expect(
      screen.getByText("Connect the notebook to include its source."),
    ).toBeInTheDocument();
  });

  it("disables include errors when there are no errors", async () => {
    store.set(
      requestClientAtom,
      MockRequestClient.create({
        getEnvironmentInfo: vi.fn().mockResolvedValue(environment),
      }),
    );
    render(<FeedbackModal onClose={vi.fn()} />, { wrapper });
    await screen.findByText("Environment details");

    expect(
      screen.getByRole("checkbox", { name: "Include errors" }),
    ).toBeDisabled();
  });

  it("prefills the GitHub issue link with the environment once loaded", async () => {
    store.set(
      requestClientAtom,
      MockRequestClient.create({
        getEnvironmentInfo: vi.fn().mockResolvedValue(environment),
      }),
    );
    render(<FeedbackModal onClose={vi.fn()} />, { wrapper });

    const link = screen.getByRole("link", { name: "Open GitHub issue" });
    expect(link).toHaveAttribute("href", Constants.bugReportUrl);

    await screen.findByText("Environment details");
    await waitFor(() => {
      const href = link.getAttribute("href") ?? "";
      expect(href).toContain("&env=");
      expect(href).toContain(encodeURIComponent('"marimo": "1.2.3"'));
    });
  });
});
