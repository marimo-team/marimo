/* Copyright 2026 Marimo. All rights reserved. */

import { act, fireEvent, render, screen } from "@testing-library/react";
import { Provider } from "jotai";
import { JsonRpcError, type useAcpClient } from "use-acp";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { TooltipProvider } from "@/components/ui/tooltip";
import { pendingAiPromptAtom } from "@/core/ai/state";
import { requestClientAtom } from "@/core/network/requests";
import { cwdAtom, filenameAtom } from "@/core/saving/file-state";
import { store } from "@/core/state/jotai";
import AgentPanel from "../agent-panel";
import {
  addSession,
  agentSessionStateAtom,
  updateSessionExternalAgentSessionId,
} from "../state";
import type { AgentConnectionState, ExternalAgentSessionId } from "../types";

type Agent = NonNullable<ReturnType<typeof useAcpClient>["agent"]>;
type InitializeResponse = Awaited<ReturnType<Agent["initialize"]>>;

const { client, connect, disconnect, setActiveSessionId } = vi.hoisted(() => {
  const client: {
    agent: ReturnType<typeof createAgent>["agent"] | null;
    connectionState: AgentConnectionState;
    activeSessionId: ExternalAgentSessionId | null;
  } = {
    agent: null,
    connectionState: { status: "connected" },
    activeSessionId: null,
  };
  return {
    client,
    connect: vi.fn().mockResolvedValue(undefined),
    disconnect: vi.fn(),
    setActiveSessionId: (sessionId: ExternalAgentSessionId | null) => {
      client.activeSessionId = sessionId;
    },
  };
});

vi.mock("use-acp", async (importOriginal) => ({
  ...(await importOriginal<typeof import("use-acp")>()),
  useAcpClient: () => ({
    ...client,
    connect,
    disconnect,
    notifications: [],
    setActiveSessionId,
    clearNotifications: vi.fn(),
  }),
}));
vi.mock("@/components/editor/ai/add-cell-with-ai", () => ({
  PromptInput: () => null,
}));
vi.mock("../session-tabs", () => ({ SessionTabs: () => null }));
vi.mock("../blocks", () => ({ ReadyToChatBlock: () => null }));

const initialized: InitializeResponse = {
  protocolVersion: 1,
  agentCapabilities: {},
};
const advertisedAuth: InitializeResponse = {
  ...initialized,
  authMethods: [{ id: "login", name: "Log in" }],
};

function createAgent() {
  const initialization = Promise.withResolvers<InitializeResponse>();
  const agent = {
    initialize: vi
      .fn<Agent["initialize"]>()
      .mockReturnValue(initialization.promise),
    authenticate: vi.fn<Agent["authenticate"]>().mockResolvedValue(undefined),
    newSession: vi.fn<Agent["newSession"]>().mockImplementation(async () => {
      client.activeSessionId = "new-session" as ExternalAgentSessionId;
      return { sessionId: "new-session" };
    }),
    loadSession: vi
      .fn<NonNullable<Agent["loadSession"]>>()
      .mockImplementation(async ({ sessionId }) => {
        client.activeSessionId = sessionId as ExternalAgentSessionId;
        return {};
      }),
    cancel: vi.fn<Agent["cancel"]>().mockResolvedValue(undefined),
    prompt: vi
      .fn<Agent["prompt"]>()
      .mockResolvedValue({ stopReason: "end_turn" }),
  };
  return { agent, initialization };
}

function renderPanel() {
  const panel = () => (
    <Provider store={store}>
      <TooltipProvider>
        <AgentPanel />
      </TooltipProvider>
    </Provider>
  );
  const view = render(panel());
  return { ...view, refresh: () => view.rerender(panel()) };
}

function expectNoSessionRequests(
  agent: ReturnType<typeof createAgent>["agent"],
) {
  expect(agent.newSession).not.toHaveBeenCalled();
  expect(agent.loadSession).not.toHaveBeenCalled();
}

describe("AgentPanel initialization", () => {
  beforeEach(() => {
    client.agent = null;
    client.activeSessionId = null;
    client.connectionState = { status: "connected" };
    store.set(requestClientAtom, MockRequestClient.create());
    store.set(filenameAtom, "notebook.py");
    store.set(cwdAtom, "/notebooks");
    store.set(pendingAiPromptAtom, null);
    store.set(
      agentSessionStateAtom,
      addSession({ sessions: [], activeTabId: null }, { agentId: "claude" }),
    );
  });

  afterEach(() => {
    store.set(pendingAiPromptAtom, null);
    store.set(agentSessionStateAtom, { sessions: [], activeTabId: null });
    store.set(filenameAtom, null);
    store.set(cwdAtom, null);
  });

  it.each([null, "saved-session"])(
    "waits for initialization before creating/loading %s",
    async (sessionId) => {
      const { agent, initialization } = createAgent();
      client.agent = agent;
      if (sessionId) {
        store.set(agentSessionStateAtom, (state) =>
          updateSessionExternalAgentSessionId(
            state,
            sessionId as ExternalAgentSessionId,
          ),
        );
      }
      const { refresh } = renderPanel();
      expect(agent.initialize).toHaveBeenCalledOnce();
      expectNoSessionRequests(agent);
      expect(
        screen.queryByRole("button", { name: "Restart" }),
      ).not.toBeInTheDocument();

      await act(async () => initialization.resolve(initialized));
      expect(agent.authenticate).not.toHaveBeenCalled();
      expect(agent.loadSession.mock.calls).toEqual(
        sessionId
          ? [
              [
                {
                  sessionId,
                  cwd: "/notebooks",
                  mcpServers: [],
                },
              ],
            ]
          : [],
      );
      expect(agent.newSession.mock.calls).toEqual(
        sessionId
          ? []
          : [
              [
                {
                  cwd: "/notebooks",
                  mcpServers: [],
                  _meta: undefined,
                },
              ],
            ],
      );
      expect(
        screen.getByRole("button", { name: "Restart" }),
      ).toBeInTheDocument();
      refresh();
      expect(
        agent.newSession.mock.calls.length +
          agent.loadSession.mock.calls.length,
      ).toBe(1);
    },
  );

  it("uses existing CLI credentials even when the agent advertises login methods", async () => {
    const { agent, initialization } = createAgent();
    agent.authenticate.mockRejectedValue(new Error("Method not implemented."));
    client.agent = agent;
    renderPanel();

    await act(async () => initialization.resolve(advertisedAuth));
    expect(agent.authenticate).not.toHaveBeenCalled();
    expect(agent.newSession).toHaveBeenCalledOnce();
  });

  it("surfaces initialization failures and offers a connection retry", async () => {
    const { agent, initialization } = createAgent();
    client.agent = agent;
    const { refresh } = renderPanel();

    await act(async () => initialization.reject(new Error("Handshake failed")));
    expect(await screen.findByText("Handshake failed")).toBeInTheDocument();
    expectNoSessionRequests(agent);
    fireEvent.click(screen.getByRole("button", { name: "Retry connection" }));
    expect(disconnect).toHaveBeenCalledOnce();
    expect(connect).toHaveBeenCalledTimes(2);

    const retried = createAgent();
    client.agent = retried.agent;
    refresh();
    expect(screen.queryByText("Handshake failed")).not.toBeInTheDocument();
    expectNoSessionRequests(retried.agent);
    await act(async () => retried.initialization.resolve(initialized));
    expect(retried.agent.newSession).toHaveBeenCalledOnce();
  });

  it("surfaces missing CLI credentials and lets the user retry after login", async () => {
    const { agent, initialization } = createAgent();
    const authError = new JsonRpcError({
      code: -32_000,
      message: "Authentication required",
      data: { message: "Run claude /login in the terminal" },
    });
    agent.newSession
      .mockRejectedValueOnce(authError)
      .mockRejectedValueOnce(authError);
    client.agent = agent;
    renderPanel();

    await act(async () => initialization.resolve(advertisedAuth));
    expect(
      await screen.findByText("Run claude /login in the terminal"),
    ).toBeInTheDocument();
    expect(agent.authenticate).not.toHaveBeenCalled();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Restart session" }));
    });
    expect(agent.newSession).toHaveBeenCalledTimes(2);
    expect(
      screen.getByText("Run claude /login in the terminal"),
    ).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Restart session" }));
    });
    expect(agent.newSession).toHaveBeenCalledTimes(3);
    expect(
      screen.queryByText("Run claude /login in the terminal"),
    ).not.toBeInTheDocument();
  });

  it("does not authenticate or start a session for an agent switched away during initialization", async () => {
    const old = createAgent();
    const next = createAgent();
    client.agent = old.agent;
    renderPanel();
    act(() => {
      client.agent = next.agent;
      store.set(agentSessionStateAtom, (state) =>
        addSession(state, { agentId: "codex" }),
      );
    });

    await act(async () => old.initialization.resolve(advertisedAuth));
    expect(old.agent.authenticate).not.toHaveBeenCalled();
    expectNoSessionRequests(old.agent);
    expectNoSessionRequests(next.agent);
    await act(async () => next.initialization.resolve(initialized));
    expect(next.agent.newSession).toHaveBeenCalledOnce();
  });

  it("ignores a late initialization error from the previous agent", async () => {
    const old = createAgent();
    const next = createAgent();
    client.agent = old.agent;
    renderPanel();
    act(() => {
      client.agent = next.agent;
      store.set(agentSessionStateAtom, (state) =>
        addSession(state, { agentId: "codex" }),
      );
    });
    await act(async () => next.initialization.resolve(initialized));
    await act(async () =>
      old.initialization.reject(new Error("Old agent failed")),
    );
    expect(screen.queryByText("Old agent failed")).not.toBeInTheDocument();
    expect(next.agent.newSession).toHaveBeenCalledOnce();
  });

  it("ignores the old handshake when the same agent reconnects before it finishes", async () => {
    const { agent, initialization } = createAgent();
    const reinitialization = Promise.withResolvers<InitializeResponse>();
    agent.initialize
      .mockReturnValueOnce(initialization.promise)
      .mockReturnValueOnce(reinitialization.promise);
    client.agent = agent;
    const { refresh } = renderPanel();

    client.connectionState = { status: "disconnected" };
    refresh();
    client.connectionState = { status: "connected" };
    refresh();
    expect(agent.initialize).toHaveBeenCalledTimes(2);
    await act(async () => initialization.resolve(advertisedAuth));
    expect(agent.authenticate).not.toHaveBeenCalled();
    expectNoSessionRequests(agent);
    await act(async () => reinitialization.resolve(initialized));
    expect(agent.newSession).toHaveBeenCalledOnce();
  });

  it("invalidates readiness on disconnect and reinitializes before resuming", async () => {
    const { agent, initialization } = createAgent();
    const reinitialization = Promise.withResolvers<InitializeResponse>();
    agent.initialize
      .mockReturnValueOnce(initialization.promise)
      .mockReturnValueOnce(reinitialization.promise);
    client.agent = agent;
    const { refresh } = renderPanel();
    await act(async () => initialization.resolve(initialized));
    expect(agent.newSession).toHaveBeenCalledOnce();

    client.connectionState = { status: "disconnected" };
    refresh();
    client.connectionState = { status: "connected" };
    refresh();
    expect(agent.loadSession).not.toHaveBeenCalled();
    await act(async () => reinitialization.resolve(initialized));
    expect(agent.loadSession).toHaveBeenCalledExactlyOnceWith({
      sessionId: "new-session",
      cwd: "/notebooks",
      mcpServers: [],
    });
    expect(agent.newSession).toHaveBeenCalledOnce();
  });

  it("keeps a queued prompt pending until initialization and session loading finish", async () => {
    const { agent, initialization } = createAgent();
    const loading = Promise.withResolvers<undefined>();
    agent.loadSession.mockImplementation(async ({ sessionId }) => {
      await loading.promise;
      client.activeSessionId = sessionId as ExternalAgentSessionId;
      return {};
    });
    client.agent = agent;
    client.activeSessionId = "saved-session" as ExternalAgentSessionId;
    store.set(agentSessionStateAtom, (state) =>
      updateSessionExternalAgentSessionId(
        state,
        "saved-session" as ExternalAgentSessionId,
      ),
    );
    store.set(pendingAiPromptAtom, { prompt: "Help", submit: true });
    renderPanel();
    expect(store.get(pendingAiPromptAtom)).toEqual({
      prompt: "Help",
      submit: true,
    });
    expect(agent.prompt).not.toHaveBeenCalled();

    await act(async () => initialization.resolve(initialized));
    expect(agent.loadSession).toHaveBeenCalledOnce();
    expect(agent.prompt).not.toHaveBeenCalled();
    expect(store.get(pendingAiPromptAtom)).toEqual({
      prompt: "Help",
      submit: true,
    });
    await act(async () => loading.resolve(undefined));
    expect(agent.prompt).toHaveBeenCalledOnce();
    expect(agent.loadSession.mock.invocationCallOrder[0]).toBeLessThan(
      agent.prompt.mock.invocationCallOrder[0],
    );
    expect(store.get(pendingAiPromptAtom)).toBeNull();
  });

  it("does not finish initialization after unmount", async () => {
    const { agent, initialization } = createAgent();
    client.agent = agent;
    const { unmount } = renderPanel();
    unmount();
    await act(async () => initialization.resolve(advertisedAuth));
    expect(agent.authenticate).not.toHaveBeenCalled();
    expectNoSessionRequests(agent);
  });
});
