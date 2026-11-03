/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Provider } from "jotai";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { cellId } from "@/__tests__/branded";
import { ModalProvider } from "@/components/modal/ImperativeModal";
import { TooltipProvider } from "@/components/ui/tooltip";
import { initialNotebookState, notebookAtom } from "@/core/cells/cells";
import type { MarimoError } from "@/core/kernel/messages";
import { viewStateAtom } from "@/core/mode";
import { connectionAtom } from "@/core/network/connection";
import { requestClientAtom } from "@/core/network/requests";
import { filenameAtom } from "@/core/saving/file-state";
import { ConnectionState } from "@/core/session/types";
import { store } from "@/core/state/jotai";
import { ReportMarimoBugButton } from "../report-marimo-bug-button";

function wrapper({ children }: PropsWithChildren) {
  return (
    <Provider store={store}>
      <TooltipProvider>
        <ModalProvider>{children}</ModalProvider>
      </TooltipProvider>
    </Provider>
  );
}

const error: MarimoError = {
  type: "exception",
  exception_type: "InternalError",
  msg: "broken invariant",
  raising_cell: null,
  is_internal: true,
  traceback: "<pre>InternalError: broken invariant</pre>",
};

describe("ReportMarimoBugButton", () => {
  beforeEach(() => {
    localStorage.clear();
    store.set(notebookAtom, initialNotebookState());
    store.set(viewStateAtom, { mode: "edit", cellAnchor: null });
    store.set(connectionAtom, { state: ConnectionState.OPEN });
    store.set(filenameAtom, "/project/example.py");
    store.set(requestClientAtom, MockRequestClient.create());
  });

  it.each<{ errors: MarimoError[] }>([
    { errors: [] },
    { errors: [{ ...error, is_internal: false }] },
    { errors: [{ ...error, is_internal: undefined }] },
    {
      errors: [{ type: "internal", msg: "redacted error", error_id: "error1" }],
    },
  ])("hides the action for unclassified errors: %j", ({ errors }) => {
    render(<ReportMarimoBugButton cellId={cellId("cell1")} errors={errors} />, {
      wrapper,
    });
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it.each(["read", "present"] as const)(
    "hides the action in %s mode",
    (mode) => {
      store.set(viewStateAtom, { mode, cellAnchor: null });
      render(
        <ReportMarimoBugButton cellId={cellId("cell1")} errors={[error]} />,
        { wrapper },
      );
      expect(screen.queryByRole("button")).not.toBeInTheDocument();
    },
  );

  it("opens a report with a snapshot of the selected error and loads diagnostics on demand", async () => {
    const getEnvironmentInfo = vi.fn().mockResolvedValue({ marimo: "1.2.3" });
    const readCode = vi.fn().mockResolvedValue({ contents: "notebook source" });
    store.set(
      requestClientAtom,
      MockRequestClient.create({ getEnvironmentInfo, readCode }),
    );
    localStorage.setItem("marimo:issue-report:include-errors", "false");
    const selectedError = { ...error };
    const { rerender } = render(
      <ReportMarimoBugButton
        cellId={cellId("cell1")}
        errors={[selectedError]}
      />,
      { wrapper },
    );
    expect(getEnvironmentInfo).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("button", { name: "Report a marimo bug" }),
    );
    await screen.findByText("Environment details");
    expect(getEnvironmentInfo).toHaveBeenCalledOnce();
    expect(readCode).not.toHaveBeenCalled();
    expect(
      screen.getByRole("checkbox", { name: "Include errors" }),
    ).toBeChecked();
    const link = screen.getByRole("link", { name: "Open GitHub issue" });
    const description = () =>
      new URL(link.getAttribute("href")!).searchParams.get("bug-description");
    expect(description()).toContain("broken invariant");
    expect(description()).toContain("InternalError: broken invariant");
    expect(link.getAttribute("href")).not.toContain("reproduction-code=");

    selectedError.msg = "new error";
    rerender(<ReportMarimoBugButton cellId={cellId("cell1")} errors={[]} />);
    expect(description()).toContain("broken invariant");
    expect(description()).not.toContain("new error");
    expect(localStorage.getItem("marimo:issue-report:include-errors")).toBe(
      "false",
    );

    fireEvent.click(screen.getByRole("checkbox", { name: "Include errors" }));
    expect(description()).toBeNull();
    fireEvent.click(
      screen.getByRole("checkbox", { name: "Include notebook code" }),
    );
    await waitFor(() => expect(readCode).toHaveBeenCalledOnce());
    await waitFor(() =>
      expect(link.getAttribute("href")).toContain("reproduction-code="),
    );
  });
});
