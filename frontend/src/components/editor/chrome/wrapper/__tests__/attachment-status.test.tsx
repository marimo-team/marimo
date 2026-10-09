/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { act, fireEvent, render, screen } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { userEvent } from "storybook/test";
import { describe, expect, it } from "vitest";
import { PAIR_PREVIEW } from "@/__tests__/fixtures/pair-preview";
import { TooltipProvider } from "@/components/ui/tooltip";
import { type Attachment, attachmentsAtom } from "@/core/attachments/state";
import { pairPreviewAtom } from "@/core/config/pair";
import { connectionAtom } from "@/core/network/connection";
import { WebSocketClosedReason, WebSocketState } from "@/core/websocket/types";
import { AttachmentStatus } from "../footer-items/attachment-status";

const AGENT: Attachment = {
  id: "a1",
  kind: "agent",
  name: "Pi",
  since: Date.now() / 1000,
};

function renderStatus(attachments: Attachment[] = [AGENT], preview = true) {
  const store = createStore();
  store.set(connectionAtom, { state: WebSocketState.OPEN });
  store.set(pairPreviewAtom, preview ? PAIR_PREVIEW : undefined);
  store.set(attachmentsAtom, attachments);
  return {
    store,
    ...render(
      <Provider store={store}>
        <TooltipProvider>
          <AttachmentStatus />
        </TooltipProvider>
      </Provider>,
    ),
  };
}

describe("AttachmentStatus", () => {
  it("renders nothing outside the preview", () => {
    expect(renderStatus([AGENT], false).container).toBeEmptyDOMElement();
  });

  it("renders nothing without agents", () => {
    expect(
      renderStatus([{ ...AGENT, kind: "client" }]).container,
    ).toBeEmptyDOMElement();
  });

  it("lists each agent by its self-described name", () => {
    renderStatus([
      AGENT,
      { ...AGENT, id: "a2", name: "Claude Code" },
      { ...AGENT, id: "c1", kind: "client", name: "Browser" },
    ]);
    expect(screen.getAllByTestId("footer-attachment-status")).toHaveLength(2);
    expect(screen.getByLabelText("Pi: Connected")).toBeInTheDocument();
    expect(screen.getByLabelText("Claude Code: Connected")).toBeInTheDocument();
    expect(screen.queryByText("Browser")).not.toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Pi: Connected"));
    expect(screen.getByText(/^Connected /)).toBeInTheDocument();
  });

  it("uses Agent when no name was supplied", () => {
    renderStatus([{ ...AGENT, name: null }]);
    expect(screen.getByLabelText("Agent: Connected")).toBeInTheDocument();
  });

  it.each(["{Enter}", " "])("opens from the keyboard with %j", async (key) => {
    const user = userEvent.setup();
    renderStatus();
    const button = screen.getByRole("button", { name: "Pi: Connected" });
    expect(button.tagName).toBe("BUTTON");
    expect(button).toHaveAttribute("type", "button");
    await user.tab();
    expect(button).toHaveFocus();
    await user.keyboard(key);
    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText(/^Connected /)).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button).toHaveFocus();
  });

  it.each([
    { state: WebSocketState.CONNECTING },
    { state: WebSocketState.CLOSING },
    { state: WebSocketState.NOT_STARTED },
    {
      state: WebSocketState.CLOSED,
      code: WebSocketClosedReason.KERNEL_DISCONNECTED,
      reason: "offline",
    },
  ])("hides connected claims while the browser is %j", (connection) => {
    const { store, container } = renderStatus();
    act(() => store.set(connectionAtom, connection));
    expect(container).toBeEmptyDOMElement();
  });

  it("removes detached agents when the list is replaced", () => {
    const { store, container } = renderStatus([
      AGENT,
      { ...AGENT, id: "a2", name: "Claude Code" },
    ]);
    act(() => store.set(attachmentsAtom, [AGENT]));
    expect(
      screen.queryByLabelText("Claude Code: Connected"),
    ).not.toBeInTheDocument();
    act(() => store.set(attachmentsAtom, []));
    expect(container).toBeEmptyDOMElement();
  });
});
