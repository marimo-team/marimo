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
import type React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/use-toast";
import type { SendResult } from "@/core/agents/messages";
import {
  type StableSessionId,
  stableSessionIdAtom,
} from "@/core/kernel/session";
import { type AppMode, initialModeAtom, viewStateAtom } from "@/core/mode";
import { API } from "@/core/network/api";
import type { Attachment } from "@/core/notebook";
import { Deferred } from "@/utils/Deferred";
import { HTTPError } from "@/utils/errors";
import { SendToAgentButton } from "../send-to-agent-button";

vi.mock("@/components/ui/use-toast", () => ({ toast: vi.fn() }));
vi.mock("@/core/network/api", () => ({ API: { post: vi.fn() } }));

const STABLE_ID = "stable/test" as StableSessionId;
const attachmentsAtom = atom<Attachment[]>([]);
vi.mock("@/core/session/active-notebook", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/core/session/active-notebook")>()),
  activeNotebookReplicaAtom: atom(() => ({ attachmentsAtom })),
}));

const AGENT: Attachment = {
  id: "a1",
  kind: "agent",
  name: "Pi",
  since: "2026-10-14T00:00:00Z",
  notebook_id: "nb-test",
  identity: "pi-thread",
};
const ROUTE = "/pair/notebooks/stable%2Ftest/messages";
const SUBMITTED: SendResult = {
  recipients: [{ agent_id: "pi-thread", status: "submitted", detail: null }],
};
const requestFor = (message: unknown) => ({
  message,
  to: "pi-thread",
  timeout: 30,
});
const REPORT = { type: "selection", rows: [1, 3] };

function renderButton({
  mode = "edit",
  attachments = [AGENT],
  stableId = STABLE_ID,
  getContent = () => REPORT,
}: {
  mode?: AppMode;
  attachments?: Attachment[];
  stableId?: StableSessionId | null;
  getContent?: () => unknown;
} = {}) {
  const store = createStore();
  store.set(initialModeAtom, mode);
  store.set(attachmentsAtom, attachments);
  store.set(stableSessionIdAtom, stableId);
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <Provider store={store}>
      <TooltipProvider>{children}</TooltipProvider>
    </Provider>
  );
  return {
    store,
    ...render(
      <SendToAgentButton getContent={getContent}>
        Send to agent
      </SendToAgentButton>,
      { wrapper },
    ),
  };
}

function send() {
  fireEvent.click(screen.getByRole("button", { name: "Send to agent" }));
}

describe("SendToAgentButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(API.post).mockResolvedValue(SUBMITTED);
    vi.mocked(toast).mockReturnValue({
      id: "notice",
      dismiss: vi.fn(),
      update: vi.fn(),
      upsert: vi.fn(),
    });
  });

  it("hides in read mode without building content", () => {
    const getContent = vi.fn(() => REPORT);
    expect(
      renderButton({
        mode: "read",
        getContent,
      }).container,
    ).toBeEmptyDOMElement();
    expect(getContent).not.toHaveBeenCalled();
  });

  it("remains available when an editor enters presentation mode", () => {
    const { store } = renderButton();
    act(() => store.set(viewStateAtom, { mode: "present", cellAnchor: null }));
    expect(screen.getByRole("button")).toBeEnabled();
  });

  it.each([
    { attachments: [] },
    { attachments: [{ ...AGENT, kind: "client" as const }] },
  ])("hides without a connected agent: %j", (options) => {
    const getContent = vi.fn(() => REPORT);
    const { container } = renderButton({
      ...options,
      getContent,
    });
    expect(container).toBeEmptyDOMElement();
    expect(getContent).not.toHaveBeenCalled();
    expect(API.post).not.toHaveBeenCalled();
  });

  it("disables sending without a stable ID", () => {
    renderButton({ stableId: null });
    expect(screen.getByRole("button")).toBeDisabled();
    send();
    expect(API.post).not.toHaveBeenCalled();
  });

  it("groups reconnecting attachments and sends to the logical agent", async () => {
    const getContent = vi.fn(() => REPORT);
    renderButton({
      attachments: [AGENT, { ...AGENT, id: "a2", name: "Claude Code" }],
      getContent,
    });
    expect(getContent).not.toHaveBeenCalled();
    send();
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith({
        title: "Submitted to Claude Code",
        duration: 3000,
      }),
    );
    expect(API.post).toHaveBeenCalledWith(
      ROUTE,
      requestFor(REPORT),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(getContent).toHaveBeenCalledOnce();
  });

  it("prevents duplicate sends while a request is pending", async () => {
    const deferred = new Deferred<SendResult>();
    vi.mocked(API.post).mockReturnValue(deferred.promise);
    renderButton();
    send();
    expect(screen.getByRole("button")).toBeDisabled();
    send();
    expect(API.post).toHaveBeenCalledOnce();
    await act(async () => deferred.resolve(SUBMITTED));
    expect(screen.getByRole("button")).toBeEnabled();
  });

  it("uses the menu's distinct labels in broadcast results", async () => {
    vi.mocked(API.post).mockResolvedValue({
      recipients: [
        { agent_id: "pi-thread", status: "submitted", detail: null },
        { agent_id: "another-thread", status: "submitted", detail: null },
      ],
    });
    renderButton({
      attachments: [AGENT, { ...AGENT, id: "a2", identity: "another-thread" }],
    });
    fireEvent.keyDown(screen.getByRole("button"), { key: "ArrowDown" });
    fireEvent.click(
      await screen.findByRole("menuitem", { name: "Send to all agents" }),
    );
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Submitted to Pi (pi-thread), Pi (another-thread)",
        }),
      ),
    );
  });

  it("offers distinct recipients and explicit broadcast through the keyboard", async () => {
    renderButton({
      attachments: [AGENT, { ...AGENT, id: "a2", identity: "another-thread" }],
    });
    fireEvent.keyDown(screen.getByRole("button"), { key: "ArrowDown" });
    const target = await screen.findByRole("menuitem", {
      name: "Pi (another-thread)",
    });
    expect(
      screen.getByRole("menuitem", { name: "Pi (pi-thread)" }),
    ).toBeVisible();
    expect(
      screen.getByRole("menuitem", { name: "Send to all agents" }),
    ).toBeVisible();
    expect(API.post).not.toHaveBeenCalled();
    fireEvent.click(target);
    await waitFor(() =>
      expect(API.post).toHaveBeenCalledWith(
        ROUTE,
        { message: REPORT, to: "another-thread", timeout: 30 },
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
    );
  });

  it("broadcasts only after an explicit choice and reports partial outcomes", async () => {
    vi.mocked(API.post).mockResolvedValue({
      recipients: [
        { agent_id: "pi-thread", status: "submitted", detail: null },
        {
          agent_id: "claude",
          status: "unknown",
          detail: "No native acceptance receipt",
        },
      ],
    });
    renderButton({
      attachments: [
        AGENT,
        { ...AGENT, id: "a2", identity: "claude", name: "Claude" },
      ],
    });
    fireEvent.keyDown(screen.getByRole("button"), { key: "ArrowDown" });
    fireEvent.click(
      await screen.findByRole("menuitem", { name: "Send to all agents" }),
    );
    await waitFor(() =>
      expect(API.post).toHaveBeenCalledWith(
        ROUTE,
        { message: REPORT, broadcast: true, timeout: 30 },
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
    );
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith(
        expect.objectContaining({
          variant: "danger",
          title: "Some messages were not confirmed",
          description: expect.stringContaining(
            "Claude: No native acceptance receipt",
          ),
        }),
      ),
    );
    expect(API.post).toHaveBeenCalledOnce();
  });

  it.each(["rejected", "unknown"])(
    "reports a %s recipient without another send",
    async (status) => {
      vi.mocked(API.post).mockResolvedValue({
        recipients: [{ agent_id: "pi-thread", status, detail: "Disconnected" }],
      });
      renderButton();
      send();
      await waitFor(() =>
        expect(toast).toHaveBeenCalledWith(
          expect.objectContaining({
            variant: "danger",
            title:
              status === "unknown"
                ? "Submission outcome unknown"
                : "Message rejected",
          }),
        ),
      );
      expect(API.post).toHaveBeenCalledOnce();
      expect(screen.getByRole("button")).toBeEnabled();
    },
  );

  it("retains the chosen target while attachment state changes", async () => {
    const deferred = new Deferred<SendResult>();
    vi.mocked(API.post).mockReturnValue(deferred.promise);
    const { store } = renderButton();
    send();
    act(() =>
      store.set(attachmentsAtom, [{ ...AGENT, id: "a2", identity: "other" }]),
    );
    expect(API.post).toHaveBeenCalledOnce();
    expect(API.post).toHaveBeenCalledWith(
      ROUTE,
      requestFor(REPORT),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    await act(async () => deferred.resolve(SUBMITTED));
    expect(API.post).toHaveBeenCalledOnce();
  });

  it("releases pending state after a producer error without dispatch", async () => {
    renderButton({
      getContent: () => {
        throw new Error("Cannot capture output");
      },
    });
    send();
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Could not send message" }),
      ),
    );
    expect(API.post).not.toHaveBeenCalled();
    expect(screen.getByRole("button")).toBeEnabled();
  });

  it("shows and hides the button as agents connect and disconnect", () => {
    const { store } = renderButton({ attachments: [] });
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    act(() => store.set(attachmentsAtom, [AGENT]));
    expect(screen.getByRole("button")).toBeEnabled();
    act(() =>
      store.set(attachmentsAtom, [
        AGENT,
        { ...AGENT, id: "a2", name: "Claude Code" },
      ]),
    );
    act(() => store.set(attachmentsAtom, [AGENT]));
    expect(screen.getByRole("button")).toBeEnabled();
    act(() => store.set(attachmentsAtom, []));
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it.each([
    [
      new HTTPError(409, "Conflict", {
        code: "no-agents",
        detail: "No agents are connected",
      }),
      "Could not send message",
      "No agents are connected",
    ],
    [
      new HTTPError(500, "Server error"),
      "Submission outcome unknown",
      "The submission outcome is unknown. Another send can duplicate the message.",
    ],
  ])(
    "reports request failures and permits retry",
    async (error, title, description) => {
      vi.mocked(API.post).mockRejectedValueOnce(error);
      renderButton();
      send();
      await waitFor(() =>
        expect(toast).toHaveBeenCalledWith({
          variant: "danger",
          title,
          description,
          duration: 5000,
        }),
      );
      expect(screen.getByRole("button")).toBeEnabled();
      send();
      await waitFor(() =>
        expect(toast).toHaveBeenCalledWith({
          title: "Submitted to Pi",
          duration: 3000,
        }),
      );
      expect(API.post).toHaveBeenCalledTimes(2);
      expect(API.post).toHaveBeenLastCalledWith(
        ROUTE,
        requestFor(REPORT),
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      );
    },
  );

  it("sends updated producer content", async () => {
    const { rerender } = renderButton();
    const updated = {
      ...REPORT,
      rows: [2],
    };
    rerender(
      <SendToAgentButton getContent={() => updated}>
        Send to agent
      </SendToAgentButton>,
    );
    send();
    await waitFor(() =>
      expect(API.post).toHaveBeenCalledWith(
        ROUTE,
        requestFor(updated),
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
    );
  });

  it.each([
    "Hello agent",
    { lens: { selection: [1, 2], chart: "scatter" } },
    [1, "two"],
    null,
  ])("accepts arbitrary producer content: %j", async (content) => {
    renderButton({
      getContent: () => content,
    });
    send();
    await waitFor(() =>
      expect(API.post).toHaveBeenCalledWith(
        ROUTE,
        requestFor(content),
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
    );
  });
});
