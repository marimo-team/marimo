/* Copyright 2026 Marimo. All rights reserved. */

import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { Provider } from "jotai";
import type { ComponentProps } from "react";
import { JsonRpcError } from "use-acp";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import type { PromptInput } from "@/components/editor/ai/add-cell-with-ai";
import { TooltipProvider } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/use-toast";
import { pendingAiPromptAtom } from "@/core/ai/state";
import { requestClientAtom } from "@/core/network/requests";
import { cwdAtom, filenameAtom } from "@/core/saving/file-state";
import { store } from "@/core/state/jotai";
import AgentPanel from "../agent-panel";
import { parseContextFromPrompt } from "../context-utils";
import {
  addSession,
  agentSessionStateAtom,
  selectedTabAtom,
  updateSessionExternalAgentSessionId,
} from "../state";
import type { ExternalAgentSessionId } from "../types";

const { agent, client } = vi.hoisted(() => {
  const agent = {
    initialize: vi.fn().mockResolvedValue({}),
    prompt: vi.fn().mockResolvedValue({ stopReason: "end_turn" }),
    cancel: vi.fn().mockResolvedValue({}),
  };
  return {
    agent,
    client: {
      agent,
      activeSessionId: "session-1",
      connectionState: { status: "connected" },
      notifications: [],
      connect: vi.fn().mockResolvedValue(undefined),
      disconnect: vi.fn(),
      setActiveSessionId: vi.fn(),
    },
  };
});

vi.mock("use-acp", async (importOriginal) => ({
  ...(await importOriginal<typeof import("use-acp")>()),
  useAcpClient: () => client,
}));

vi.mock("@/components/editor/ai/add-cell-with-ai", () => ({
  PromptInput: ({
    value,
    onChange,
    onAddFiles,
    onSubmit,
  }: ComponentProps<typeof PromptInput>) => (
    <>
      <textarea
        aria-label="Prompt"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            onSubmit(undefined, value);
          }
        }}
      />
      <input
        type="file"
        aria-label="Attachment"
        onChange={(event) => onAddFiles?.([...(event.target.files ?? [])])}
      />
    </>
  ),
}));
vi.mock("../session-tabs", () => ({ SessionTabs: () => null }));
vi.mock("../blocks", () => ({ ReadyToChatBlock: () => null }));
vi.mock("../context-utils", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../context-utils")>()),
  parseContextFromPrompt: vi
    .fn()
    .mockResolvedValue({ contextBlocks: [], attachmentBlocks: [] }),
}));
vi.mock("@/components/ui/use-toast", () => ({ toast: vi.fn() }));

async function renderPanel() {
  const view = render(
    <Provider store={store}>
      <TooltipProvider>
        <AgentPanel />
      </TooltipProvider>
    </Provider>,
  );
  await screen.findByRole("textbox", { name: "Prompt" });
  return view;
}

function submitPrompt(prompt = "Explain this notebook") {
  fireEvent.change(screen.getByRole("textbox", { name: "Prompt" }), {
    target: { value: prompt },
  });
  fireEvent.keyDown(screen.getByRole("textbox", { name: "Prompt" }), {
    key: "Enter",
  });
}

describe("AgentPanel prompt submission", () => {
  beforeEach(() => {
    agent.prompt.mockReset().mockResolvedValue({ stopReason: "end_turn" });
    vi.mocked(parseContextFromPrompt).mockReset().mockResolvedValue({
      contextBlocks: [],
      attachmentBlocks: [],
    });
    store.set(requestClientAtom, MockRequestClient.create());
    store.set(filenameAtom, "notebook.py");
    store.set(cwdAtom, "/notebooks");
    store.set(pendingAiPromptAtom, null);
    store.set(
      agentSessionStateAtom,
      updateSessionExternalAgentSessionId(
        addSession({ sessions: [], activeTabId: null }, { agentId: "claude" }),
        "session-1" as ExternalAgentSessionId,
      ),
    );
  });

  afterEach(() => {
    store.set(pendingAiPromptAtom, null);
    store.set(agentSessionStateAtom, { sessions: [], activeTabId: null });
    store.set(filenameAtom, null);
    store.set(cwdAtom, null);
  });

  it("preserves the draft, attachment and title when the notebook is unnamed", async () => {
    store.set(filenameAtom, null);
    await renderPanel();
    const title = store.get(selectedTabAtom)?.title;
    fireEvent.change(screen.getByLabelText("Attachment"), {
      target: {
        files: [new File(["notes"], "notes.txt", { type: "text/plain" })],
      },
    });
    submitPrompt();

    expect(toast).toHaveBeenCalledWith({
      title: "Notebook must be named",
      description: "Please name the notebook to use the agent",
      variant: "danger",
    });
    expect(agent.prompt).not.toHaveBeenCalled();
    expect(screen.getByRole("textbox", { name: "Prompt" })).toHaveValue(
      "Explain this notebook",
    );
    expect(screen.getByText("notes.txt")).toBeInTheDocument();
    expect(store.get(selectedTabAtom)?.title).toBe(title);
    expect(screen.queryByText("Agent is working...")).not.toBeInTheDocument();

    act(() => store.set(filenameAtom, "notebook.py"));
    fireEvent.keyDown(screen.getByRole("textbox", { name: "Prompt" }), {
      key: "Enter",
    });
    await waitFor(() => expect(agent.prompt).toHaveBeenCalledOnce());
    expect(agent.prompt).toHaveBeenCalledWith({
      sessionId: "session-1",
      prompt: expect.arrayContaining([
        { type: "text", text: "Explain this notebook" },
        expect.objectContaining({ type: "resource_link", name: "notes.txt" }),
      ]),
    });
    await waitFor(() =>
      expect(screen.queryByText("Agent is working...")).not.toBeInTheDocument(),
    );
  });

  it.each([new Error("Agent unavailable"), "Agent unavailable"])(
    "shows a rejected prompt and allows another submission after dismissal (%s)",
    async (error) => {
      agent.prompt.mockRejectedValueOnce(error);
      await renderPanel();
      submitPrompt();

      expect(await screen.findByText(/Agent unavailable/)).toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
      expect(screen.queryByText(/Agent unavailable/)).not.toBeInTheDocument();
      submitPrompt("Try again");
      await waitFor(() => expect(agent.prompt).toHaveBeenCalledTimes(2));
      await waitFor(() =>
        expect(
          screen.queryByText("Agent is working..."),
        ).not.toBeInTheDocument(),
      );
    },
  );

  it("preserves the existing authentication error action and detail", async () => {
    agent.prompt.mockRejectedValueOnce(
      new JsonRpcError({
        code: -32_000,
        message: "Authentication required",
        data: { message: "Sign in to the agent" },
      }),
    );
    await renderPanel();
    submitPrompt();

    expect(await screen.findByText("Sign in to the agent")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Restart session" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Dismiss" }),
    ).not.toBeInTheDocument();
  });

  it("clears busy state and reports failures while preparing prompt context", async () => {
    vi.mocked(parseContextFromPrompt).mockRejectedValueOnce(
      new Error("Context unavailable"),
    );
    await renderPanel();
    submitPrompt();

    expect(await screen.findByText("Context unavailable")).toBeInTheDocument();
    expect(agent.prompt).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByText("Agent is working...")).not.toBeInTheDocument();
    submitPrompt();
    await waitFor(() => expect(agent.prompt).toHaveBeenCalledOnce());
  });

  it("reports failures from a queued prompt through the same handler", async () => {
    agent.prompt.mockRejectedValueOnce(new Error("Queued prompt failed"));
    await renderPanel();
    act(() =>
      store.set(pendingAiPromptAtom, {
        prompt: "Help with this cell",
        submit: true,
      }),
    );

    expect(await screen.findByText("Queued prompt failed")).toBeInTheDocument();
    expect(store.get(pendingAiPromptAtom)).toBeNull();
    expect(agent.prompt).toHaveBeenCalledWith({
      sessionId: "session-1",
      prompt: expect.arrayContaining([
        { type: "text", text: "Help with this cell" },
      ]),
    });
  });

  it("clears busy state when a cancelled prompt settles", async () => {
    const response = Promise.withResolvers<{ stopReason: string }>();
    agent.prompt.mockReturnValueOnce(response.promise);
    await renderPanel();
    submitPrompt();
    await waitFor(() => expect(agent.prompt).toHaveBeenCalledOnce());
    expect(screen.getByText("Agent is working...")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Stop" }));
    await act(async () => response.resolve({ stopReason: "cancelled" }));
    expect(agent.cancel).toHaveBeenCalledWith({ sessionId: "session-1" });
    expect(screen.queryByText("Agent is working...")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Dismiss" }),
    ).not.toBeInTheDocument();
  });
});
