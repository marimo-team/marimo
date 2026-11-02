/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { atom, createStore, Provider } from "jotai";
import { userEvent } from "storybook/test";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PAIR_CONFIG } from "@/__tests__/fixtures/pair-config";
import { TooltipProvider } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/use-toast";
import type { Attachment } from "@/core/notebook/attachments";
import { pairConfigAtom } from "@/core/config/pair";
import {
  type StableSessionId,
  stableSessionIdAtom,
} from "@/core/kernel/session";
import { API } from "@/core/network/api";
import { connectionAtom } from "@/core/network/connection";
import { ConnectionState } from "@/core/session/types";
import { Deferred } from "@/utils/Deferred";
import { AttachmentStatus } from "../footer-items/attachment-status";

vi.mock("@/components/ui/use-toast", () => ({ toast: vi.fn() }));
vi.mock("@/core/network/api", () => ({ API: { post: vi.fn() } }));

const attachmentsAtom = atom<Attachment[]>([]);
vi.mock("@/core/session/active-notebook", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/core/session/active-notebook")>()),
  activeNotebookReplicaAtom: atom(() => ({ attachmentsAtom })),
}));

const AGENT: Attachment = {
  id: "a1",
  kind: "agent",
  name: "Pi",
  since: new Date().toISOString(),
  notebook_id: "nb-one",
};

function renderStatus(attachments: Attachment[] = [AGENT], preview = true) {
  const store = createStore();
  store.set(connectionAtom, { state: ConnectionState.OPEN });
  store.set(pairConfigAtom, { ...PAIR_CONFIG, hostEnabled: preview });
  store.set(attachmentsAtom, attachments);
  store.set(stableSessionIdAtom, "stable/test" as StableSessionId);
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
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(API.post).mockResolvedValue("");
    vi.mocked(toast).mockReturnValue({
      id: "notice",
      dismiss: vi.fn(),
      update: vi.fn(),
      upsert: vi.fn(),
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders nothing when host is disabled", () => {
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
    expect(screen.getAllByTestId("footer-attachment-status")).toHaveLength(1);
    expect(screen.getByLabelText("2 agents connected")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Pi" })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Claude Code" }),
    ).toBeInTheDocument();
    expect(screen.getByText("a1")).toBeInTheDocument();
    expect(screen.getByText("a2")).toBeInTheDocument();
    expect(screen.queryByText("Browser")).not.toBeInTheDocument();
    expect(screen.getAllByText(/^Connected /)).toHaveLength(2);
  });

  it("uses Agent when no name was supplied", () => {
    renderStatus([{ ...AGENT, name: null }]);
    expect(screen.getByLabelText("Agent connected")).toBeInTheDocument();
  });

  it.each(["{Enter}", " "])("opens from the keyboard with %j", async (key) => {
    vi.useFakeTimers();
    renderStatus();
    act(() => vi.advanceTimersByTime(3000));
    vi.useRealTimers();
    const user = userEvent.setup();
    const button = screen.getByRole("button", { name: "Pi connected" });
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

  it("opens for three seconds on connection without moving editor focus", () => {
    vi.useFakeTimers();
    const { store } = renderStatus([]);
    const editor = document.createElement("textarea");
    document.body.append(editor);
    editor.focus();
    act(() => store.set(attachmentsAtom, [AGENT]));
    const trigger = screen.getByRole("button", { name: "Pi connected" });
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(editor).toHaveFocus();
    act(() => vi.advanceTimersByTime(3000));
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(editor).toHaveFocus();
    editor.remove();
  });

  it("reopens on a new agent but not a metadata update or disconnection", () => {
    vi.useFakeTimers();
    const { store } = renderStatus();
    act(() => vi.advanceTimersByTime(3000));
    act(() => store.set(attachmentsAtom, [{ ...AGENT, name: "New name" }]));
    expect(screen.getByLabelText("New name connected")).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    act(() => store.set(attachmentsAtom, [AGENT, { ...AGENT, id: "a2" }]));
    expect(screen.getByLabelText("2 agents connected")).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    act(() => vi.advanceTimersByTime(3000));
    act(() => store.set(attachmentsAtom, [AGENT]));
    expect(screen.getByLabelText("Pi connected")).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("keeps manually opened details open past the automatic timeout", () => {
    vi.useFakeTimers();
    renderStatus();
    const trigger = screen.getByLabelText("Pi connected");
    fireEvent.click(trigger);
    fireEvent.click(trigger);
    act(() => vi.advanceTimersByTime(5000));
    expect(trigger).toHaveAttribute("aria-expanded", "true");
  });

  it("keeps manual confirmation open when another agent connects", () => {
    vi.useFakeTimers();
    const { store } = renderStatus();
    const trigger = screen.getByLabelText("Pi connected");
    fireEvent.click(trigger);
    fireEvent.click(trigger);
    fireEvent.click(screen.getByRole("button", { name: "Disconnect Pi" }));
    act(() =>
      store.set(attachmentsAtom, [
        AGENT,
        { ...AGENT, id: "a2", name: "Claude" },
      ]),
    );
    act(() => vi.advanceTimersByTime(5000));
    expect(
      screen.getByRole("button", { name: "Confirm disconnect Pi" }),
    ).toBeInTheDocument();
    expect(API.post).not.toHaveBeenCalled();
  });

  it("keeps focused details open when another agent connects", () => {
    vi.useFakeTimers();
    const { store } = renderStatus();
    act(() => screen.getByRole("button", { name: "Disconnect Pi" }).focus());
    act(() => store.set(attachmentsAtom, [AGENT, { ...AGENT, id: "a2" }]));
    act(() => vi.advanceTimersByTime(5000));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("keeps hovered details open when another agent connects", () => {
    vi.useFakeTimers();
    const { store } = renderStatus();
    fireEvent.pointerEnter(screen.getByRole("dialog"));
    act(() => store.set(attachmentsAtom, [AGENT, { ...AGENT, id: "a2" }]));
    act(() => vi.advanceTimersByTime(5000));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("pauses the automatic close while the pointer is over the details", () => {
    vi.useFakeTimers();
    renderStatus();
    const details = screen.getByRole("dialog");
    fireEvent.pointerEnter(details);
    act(() => vi.advanceTimersByTime(5000));
    expect(screen.getByLabelText("Pi connected")).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    fireEvent.pointerLeave(details);
    act(() => vi.advanceTimersByTime(3000));
    expect(screen.getByLabelText("Pi connected")).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("groups identities while keeping separate attachment rows", () => {
    renderStatus([
      { ...AGENT, identity: "same" },
      { ...AGENT, id: "a2", identity: "same" },
    ]);
    expect(screen.getByLabelText("Pi connected")).toBeInTheDocument();
    expect(
      screen.getAllByRole("button", { name: "Disconnect Pi" }),
    ).toHaveLength(2);
    for (const text of screen.getAllByText(/^Connected /)) {
      expect(text).not.toHaveTextContent("Invalid Date");
    }
  });

  it("keeps the popover closed across a same-identity reconnect gap", () => {
    vi.useFakeTimers();
    const { store } = renderStatus([{ ...AGENT, identity: "same" }]);
    act(() => vi.advanceTimersByTime(3000));
    act(() => store.set(attachmentsAtom, []));
    act(() =>
      store.set(attachmentsAtom, [{ ...AGENT, id: "a2", identity: "same" }]),
    );
    expect(screen.getByLabelText("Pi connected")).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("disconnects only the selected attachment and waits for the server update", async () => {
    const { store } = renderStatus([
      AGENT,
      { ...AGENT, id: "a2", name: "Codex" },
    ]);
    fireEvent.click(screen.getByRole("button", { name: "Disconnect Pi" }));
    expect(API.post).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("button", { name: "Confirm disconnect Pi" }),
    );
    await waitFor(() =>
      expect(API.post).toHaveBeenCalledWith(
        "/pair/notebooks/stable%2Ftest/attachments/detach",
        { attachment_id: "a1" },
      ),
    );
    expect(screen.getByLabelText("2 agents connected")).toBeInTheDocument();
    act(() =>
      store.set(attachmentsAtom, [{ ...AGENT, id: "a2", name: "Codex" }]),
    );
    expect(screen.getByLabelText("Codex connected")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Disconnect Pi" }),
    ).not.toBeInTheDocument();
  });

  it("disables duplicate disconnects while pending", async () => {
    const deferred = new Deferred<string>();
    vi.mocked(API.post).mockReturnValue(deferred.promise);
    renderStatus();
    const button = screen.getByRole("button", { name: "Disconnect Pi" });
    fireEvent.click(button);
    fireEvent.click(
      screen.getByRole("button", { name: "Confirm disconnect Pi" }),
    );
    expect(button).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Cancel disconnect Pi" }),
    ).toBeDisabled();
    fireEvent.click(button);
    expect(API.post).toHaveBeenCalledOnce();
    await act(async () => deferred.resolve(""));
  });

  it("shows disconnect failures and retains the attachment", async () => {
    vi.mocked(API.post).mockRejectedValue(new Error("offline"));
    renderStatus();
    fireEvent.click(screen.getByRole("button", { name: "Disconnect Pi" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Confirm disconnect Pi" }),
    );
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith({
        variant: "danger",
        title: "Could not disconnect Pi",
        duration: 5000,
      }),
    );
    expect(screen.getByLabelText("Pi connected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Disconnect Pi" })).toBeEnabled();
  });

  it("cancels confirmation without disconnecting and restores focus", () => {
    renderStatus();
    fireEvent.click(screen.getByRole("button", { name: "Disconnect Pi" }));
    expect(screen.getByText("Disconnect?")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Confirm disconnect Pi" }),
    ).toBeEnabled();
    fireEvent.click(
      screen.getByRole("button", { name: "Cancel disconnect Pi" }),
    );
    expect(API.post).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Disconnect Pi" })).toHaveFocus();
    expect(
      screen.queryByRole("button", { name: "Confirm disconnect Pi" }),
    ).not.toBeInTheDocument();
  });

  it("disables disconnect without a stable session ID", () => {
    const { store } = renderStatus();
    act(() => store.set(stableSessionIdAtom, null));
    expect(
      screen.getByRole("button", { name: "Disconnect Pi" }),
    ).toBeDisabled();
  });

  it("removes detached agents when the list is replaced", () => {
    const { store, container } = renderStatus([
      AGENT,
      { ...AGENT, id: "a2", name: "Claude Code" },
    ]);
    act(() => store.set(attachmentsAtom, [AGENT]));
    expect(
      screen.queryByRole("heading", { name: "Claude Code" }),
    ).not.toBeInTheDocument();
    act(() => store.set(attachmentsAtom, []));
    expect(container).toBeEmptyDOMElement();
  });
});
