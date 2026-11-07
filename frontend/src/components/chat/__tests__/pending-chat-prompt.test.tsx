/* Copyright 2026 Marimo. All rights reserved. */

import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { createStore, Provider } from "jotai";
import type { UIMessage } from "ai";
import type { ComponentProps } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { PromptInput } from "@/components/editor/ai/prompt-input";
import { resolveChatContext } from "@/components/editor/ai/completion-utils";
import { toast } from "@/components/ui/use-toast";
import { chatStateAtom, pendingAiPromptAtom } from "@/core/ai/state";
import { userConfigAtom } from "@/core/config/config";
import ChatPanel from "../chat-panel";

const { sendMessage, messages } = vi.hoisted(() => ({
  sendMessage: vi.fn(),
  messages: new Array<UIMessage>(),
}));

vi.mock("@ai-sdk/react", () => ({
  useChat: ({ id }: { id: string }) => ({
    id,
    messages,
    sendMessage,
    status: "ready",
    stop: vi.fn(),
    regenerate: vi.fn(),
    addToolOutput: vi.fn(),
    addToolApprovalResponse: vi.fn(),
  }),
}));

vi.mock("@/core/config/config", async (importOriginal) => {
  const { atom } = await import("jotai");
  return {
    ...(await importOriginal<typeof import("@/core/config/config")>()),
    aiModelConfiguredAtom: atom(true),
  };
});

vi.mock("@/core/ai/model-registry", () => ({
  getKnownModelMaps: () => ({
    modelMap: new Map([["openai/text-only", { input_types: ["text"] }]]),
  }),
}));

vi.mock("@/core/ai/config", () => ({
  useAIConfigActions: () => ({ saveModeChange: vi.fn() }),
}));
vi.mock("@/core/ai/staged-cells", () => ({
  useStagedAICellsActions: () => ({ addStagedCell: vi.fn() }),
}));
vi.mock("@/core/cells/actions", () => ({
  useCellActions: () => ({ createCell: vi.fn() }),
}));
vi.mock("@/core/network/requests", () => ({
  useRequestClient: () => ({ invokeAiTool: vi.fn() }),
}));
vi.mock("@/core/runtime/config", () => ({
  useRuntimeManager: () => ({
    getAiURL: () => new URL("http://localhost/api/ai/chat"),
    headers: () => ({}),
  }),
}));
vi.mock("@/components/app-config/state", () => ({
  useOpenSettingsToTab: () => ({ handleClick: vi.fn() }),
}));
vi.mock("@/components/editor/actions/pair-with-agent", () => ({
  PairWithAgentBanner: () => null,
  usePairWithAgentModal: () => vi.fn(),
}));
vi.mock("@/components/editor/chrome/wrapper/pending-ai-cells", () => ({
  PendingAICells: () => null,
}));
vi.mock("@/components/ai/ai-model-dropdown", () => ({
  AIModelDropdown: () => null,
}));
vi.mock("../chat-history-popover", () => ({ ChatHistoryPopover: () => null }));
vi.mock("../capabilities-popover", () => ({ CapabilitiesPopover: () => null }));
vi.mock("../notebook-access-selector", () => ({
  NotebookAccessSelector: () => null,
}));
vi.mock("../chat-display", () => ({
  renderUIMessage: () => null,
  getAnswerText: () => "",
}));
vi.mock("@/components/mcp/mcp-status-indicator", () => ({
  MCPStatusIndicator: () => null,
}));
vi.mock("@/components/ui/use-toast", () => ({ toast: vi.fn() }));

vi.mock("@/components/editor/ai/prompt-input", () => ({
  PromptInput: ({
    value,
    onChange,
    inputRef,
  }: ComponentProps<typeof PromptInput>) => (
    <textarea
      aria-label={inputRef ? "Prompt" : "Message"}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  ),
}));

vi.mock("@/components/editor/ai/completion-utils", async (importOriginal) => ({
  ...(await importOriginal<
    typeof import("@/components/editor/ai/completion-utils")
  >()),
  resolveChatContext: vi.fn(),
}));

function setup() {
  const store = createStore();
  store.set(userConfigAtom, (config) => ({
    ...config,
    ai: {
      ...config.ai,
      models: {
        custom_models: [],
        displayed_models: [],
        ...config.ai?.models,
        chat_model: "openai/text-only",
      },
    },
  }));
  store.set(chatStateAtom, { chats: new Map(), activeChatId: null });
  render(
    <Provider store={store}>
      <ChatPanel />
    </Provider>,
  );
  return store;
}

describe("pending chat prompts", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    messages.length = 0;
    sendMessage.mockReset();
    vi.stubGlobal("requestAnimationFrame", () => 0);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it.each(["new", "existing"])(
    "preserves the draft and attachments after a read failure (%s chat)",
    async (chat) => {
      vi.mocked(resolveChatContext).mockResolvedValue({
        contextPart: null,
        attachments: [],
      });
      sendMessage.mockImplementation(
        (message: { parts: UIMessage["parts"] }) => {
          messages.push({
            id: `sent-${messages.length}`,
            role: "user",
            parts: message.parts,
          });
        },
      );
      const store = setup();
      if (chat === "existing") {
        act(() =>
          store.set(pendingAiPromptAtom, { prompt: "hello", submit: true }),
        );
        await screen.findByRole("button", { name: "Edit message" });
        sendMessage.mockClear();
      }

      const fileInput =
        document.querySelector<HTMLInputElement>('input[type="file"]');
      if (!fileInput) {
        throw new Error("Missing attachment input");
      }
      fireEvent.change(fileInput, {
        target: {
          files: [new File(["hello"], "notes.txt", { type: "text/plain" })],
        },
      });
      const attachmentPill = await screen.findByText("notes.txt");
      fireEvent.change(screen.getByRole("textbox", { name: "Prompt" }), {
        target: { value: "read my notes" },
      });
      const chatState = store.get(chatStateAtom);
      const read = vi
        .spyOn(FileReader.prototype, "readAsDataURL")
        .mockImplementation(function (this: FileReader) {
          this.dispatchEvent(new Event("error"));
        });

      fireEvent.click(screen.getByRole("button", { name: "Submit" }));

      await waitFor(() =>
        expect(toast).toHaveBeenCalledWith({
          title: "Could not read attachments",
          description: "Try selecting the files again.",
          variant: "danger",
        }),
      );
      expect(sendMessage).not.toHaveBeenCalled();
      expect(store.get(chatStateAtom)).toEqual(chatState);
      expect(screen.getByRole("textbox", { name: "Prompt" })).toHaveValue(
        "read my notes",
      );
      expect(attachmentPill).toBeInTheDocument();

      read.mockRestore();
      fireEvent.click(screen.getByRole("button", { name: "Submit" }));

      await waitFor(() =>
        expect(sendMessage).toHaveBeenCalledExactlyOnceWith({
          role: "user",
          parts: [
            { type: "text", text: "read my notes" },
            {
              type: "file",
              filename: "notes.txt",
              mediaType: "text/plain",
              url: "data:text/plain;base64,aGVsbG8=",
            },
          ],
        }),
      );
      expect(screen.getByRole("textbox", { name: "Prompt" })).toHaveValue("");
      expect(attachmentPill).not.toBeInTheDocument();
    },
  );

  it("keeps a rejected pending prompt as a draft without creating an empty chat", async () => {
    vi.mocked(resolveChatContext).mockResolvedValue({
      contextPart: null,
      attachments: [
        {
          type: "file",
          mediaType: "image/png",
          filename: "cell.png",
          url: "data:image/png;base64,aW1hZ2U=",
        },
      ],
    });
    const store = setup();
    fireEvent.change(screen.getByRole("textbox", { name: "Prompt" }), {
      target: { value: "existing draft" },
    });

    act(() =>
      store.set(pendingAiPromptAtom, {
        prompt: "describe @cell",
        submit: true,
      }),
    );

    await waitFor(() =>
      expect(screen.getByRole("textbox", { name: "Prompt" })).toHaveValue(
        "existing draft describe @cell",
      ),
    );
    expect(store.get(chatStateAtom)).toEqual({
      chats: new Map(),
      activeChatId: null,
    });
    expect(store.get(pendingAiPromptAtom)).toBeNull();
    expect(sendMessage).not.toHaveBeenCalled();
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Unsupported attachment" }),
    );
  });

  it("creates a chat and sends a supported pending prompt", async () => {
    vi.mocked(resolveChatContext).mockResolvedValue({
      contextPart: null,
      attachments: [],
    });
    const store = setup();

    act(() =>
      store.set(pendingAiPromptAtom, { prompt: "hello", submit: true }),
    );

    await waitFor(() =>
      expect(sendMessage).toHaveBeenCalledExactlyOnceWith({
        role: "user",
        parts: [{ type: "text", text: "hello" }],
      }),
    );
    expect(store.get(chatStateAtom).activeChatId).toEqual(expect.any(String));
    expect(
      [...store.get(chatStateAtom).chats.values()].map((chat) => ({
        id: chat.id,
        title: chat.title,
      })),
    ).toEqual([{ id: store.get(chatStateAtom).activeChatId, title: "hello" }]);
  });

  it("queues prompts between requests while the assistant's tool is still running", async () => {
    vi.mocked(resolveChatContext).mockResolvedValue({
      contextPart: null,
      attachments: [],
    });
    sendMessage.mockImplementationOnce(() => {
      messages.push({
        id: "assistant-1",
        role: "assistant",
        parts: [
          {
            type: "tool-execute_code",
            toolCallId: "call-1",
            state: "input-available",
            input: { code: "print(1)" },
          },
        ],
      });
    });
    const store = setup();
    act(() =>
      store.set(pendingAiPromptAtom, { prompt: "run my code", submit: true }),
    );
    await screen.findByRole("button", { name: "Stop" });

    act(() =>
      store.set(pendingAiPromptAtom, {
        prompt: "then explain it",
        submit: true,
      }),
    );

    await screen.findByText("then explain it");
    expect(sendMessage).toHaveBeenCalledExactlyOnceWith({
      role: "user",
      parts: [{ type: "text", text: "run my code" }],
    });
    expect(
      screen.queryByRole("button", { name: "Send" }),
    ).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Remove queued message" }),
    );
    expect(screen.queryByText("then explain it")).not.toBeInTheDocument();
    expect(sendMessage).toHaveBeenCalledOnce();
  });

  it("carries over the latest draft typed while context is resolving", async () => {
    const context =
      Promise.withResolvers<Awaited<ReturnType<typeof resolveChatContext>>>();
    vi.mocked(resolveChatContext).mockReturnValueOnce(context.promise);
    sendMessage.mockImplementationOnce(
      (message: { parts: UIMessage["parts"] }) => {
        messages.push({
          id: "sent-message",
          role: "user",
          parts: message.parts,
        });
      },
    );
    const store = setup();
    act(() =>
      store.set(pendingAiPromptAtom, { prompt: "hello", submit: true }),
    );
    await waitFor(() =>
      expect(resolveChatContext).toHaveBeenCalledWith("hello"),
    );

    fireEvent.change(screen.getByRole("textbox", { name: "Prompt" }), {
      target: { value: "typed while waiting" },
    });
    await act(async () => {
      context.resolve({ contextPart: null, attachments: [] });
      await context.promise;
    });

    expect(screen.getByRole("textbox", { name: "Prompt" })).toHaveValue(
      "typed while waiting",
    );
    expect(sendMessage).toHaveBeenCalledOnce();
  });

  it("does not start the chat twice when two pending prompts resolve", async () => {
    const first =
      Promise.withResolvers<Awaited<ReturnType<typeof resolveChatContext>>>();
    const second =
      Promise.withResolvers<Awaited<ReturnType<typeof resolveChatContext>>>();
    vi.mocked(resolveChatContext)
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);
    const store = setup();
    act(() =>
      store.set(pendingAiPromptAtom, { prompt: "first", submit: true }),
    );
    await waitFor(() =>
      expect(resolveChatContext).toHaveBeenCalledWith("first"),
    );
    act(() =>
      store.set(pendingAiPromptAtom, { prompt: "second", submit: true }),
    );
    await waitFor(() =>
      expect(resolveChatContext).toHaveBeenCalledWith("second"),
    );

    await act(async () => {
      first.resolve({ contextPart: null, attachments: [] });
      await first.promise;
    });
    await act(async () => {
      second.resolve({ contextPart: null, attachments: [] });
      await second.promise;
    });

    expect(sendMessage).toHaveBeenCalledTimes(2);
    expect(
      [...store.get(chatStateAtom).chats.values()].map((chat) => chat.title),
    ).toEqual(["first"]);
  });
});
