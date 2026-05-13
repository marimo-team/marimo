/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { fireEvent, render } from "@testing-library/react";
import { createStore, Provider as JotaiProvider } from "jotai";
import type React from "react";
import { describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { viewStateAtom } from "@/core/mode";
import {
  type ConnectionStatus,
  WebSocketClosedReason,
  WebSocketState,
} from "@/core/websocket/types";
import { StatusOverlay } from "../status";

function renderOverlay(
  connection: ConnectionStatus,
  onReconnect?: () => void,
): ReturnType<typeof render> {
  const store = createStore();
  store.set(viewStateAtom, { mode: "edit", cellAnchor: null });
  const wrapper: React.FC<React.PropsWithChildren> = ({ children }) => (
    <JotaiProvider store={store}>
      <TooltipProvider>{children}</TooltipProvider>
    </JotaiProvider>
  );
  return render(
    <StatusOverlay
      connection={connection}
      isRunning={false}
      onReconnect={onReconnect}
    />,
    { wrapper },
  );
}

describe("StatusOverlay disconnect indicator", () => {
  it("invokes onReconnect when the disconnect icon is clicked", () => {
    const onReconnect = vi.fn();
    const { getByTestId } = renderOverlay(
      {
        state: WebSocketState.CLOSED,
        code: WebSocketClosedReason.KERNEL_DISCONNECTED,
        reason: "kernel not found",
      },
      onReconnect,
    );

    const icon = getByTestId("disconnected-indicator") as HTMLButtonElement;
    expect(icon.tagName).toBe("BUTTON");
    expect(icon.disabled).toBe(false);
    expect(icon.getAttribute("aria-label")).toBe("Reconnect to app");
    fireEvent.click(icon);
    expect(onReconnect).toHaveBeenCalledTimes(1);
  });

  it("renders a disabled button when no onReconnect is provided", () => {
    const { getByTestId } = renderOverlay({
      state: WebSocketState.CLOSED,
      code: WebSocketClosedReason.KERNEL_DISCONNECTED,
      reason: "kernel not found",
    });

    const button = getByTestId("disconnected-indicator");
    expect((button as HTMLButtonElement).disabled).toBe(true);
  });

  it.each([
    [
      WebSocketClosedReason.MALFORMED_QUERY,
      "the kernel did not recognize a request; please file a bug with marimo",
    ],
    [
      WebSocketClosedReason.KERNEL_STARTUP_ERROR,
      "Failed to start kernel sandbox",
    ],
  ])(
    "renders a disabled button for non-recoverable close reason %s",
    (code, reason) => {
      const onReconnect = vi.fn();
      const { getByTestId } = renderOverlay(
        { state: WebSocketState.CLOSED, code, reason },
        onReconnect,
      );

      const button = getByTestId("disconnected-indicator") as HTMLButtonElement;
      expect(button.disabled).toBe(true);
      fireEvent.click(button);
      expect(onReconnect).not.toHaveBeenCalled();
    },
  );

  it("does not render the disconnect icon when another tab has taken over", () => {
    const onReconnect = vi.fn();
    const { queryByTestId } = renderOverlay(
      {
        state: WebSocketState.CLOSED,
        code: WebSocketClosedReason.ALREADY_RUNNING,
        reason: "another browser tab is already connected to the kernel",
        canTakeover: true,
      },
      onReconnect,
    );

    expect(queryByTestId("disconnected-indicator")).toBeNull();
  });
});
