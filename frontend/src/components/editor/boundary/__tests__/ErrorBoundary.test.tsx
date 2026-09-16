/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { viewStateAtom } from "@/core/mode";
import { connectionAtom } from "@/core/network/connection";
import { requestClientAtom } from "@/core/network/requests";
import type { EnvironmentInfo } from "@/core/network/types";
import { filenameAtom } from "@/core/saving/file-state";
import { store } from "@/core/state/jotai";
import { WebSocketState } from "@/core/websocket/types";
import { ErrorBoundary } from "../ErrorBoundary";

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

function CrashingChild(): never {
  throw new Error("cell output crashed");
}

describe("ErrorBoundary report dialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    store.set(viewStateAtom, { mode: "edit", cellAnchor: null });
    store.set(connectionAtom, { state: WebSocketState.OPEN });
    store.set(filenameAtom, "/project/example.py");
  });

  afterEach(() => {
    store.set(requestClientAtom, null);
  });

  it("opens the report modal after a child render exception", async () => {
    const getEnvironmentInfo = vi.fn().mockResolvedValue(environment);
    store.set(
      requestClientAtom,
      MockRequestClient.create({ getEnvironmentInfo }),
    );

    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <CrashingChild />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Something went wrong")).toBeVisible();
    expect(screen.getByText("cell output crashed")).toBeVisible();
    expect(screen.getByTestId("reset-error-boundary-button")).toBeVisible();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(getEnvironmentInfo).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Report an issue" }));

    const dialog = await screen.findByRole("dialog");
    await screen.findByText("Environment details");
    expect(dialog).toHaveTextContent("Report an issue");
    await waitFor(() => expect(getEnvironmentInfo).toHaveBeenCalledOnce());

    consoleError.mockRestore();
  });
});
