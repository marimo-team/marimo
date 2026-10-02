/* Copyright 2026 Marimo. All rights reserved. */

import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { CellId } from "@/core/cells/ids";
import { AiCompletionEditor } from "../ai-completion-editor";

vi.mock("@ai-sdk/react", () => ({
  useChat: () => ({ status: "streaming", sendMessage: vi.fn(), stop: vi.fn() }),
}));
vi.mock("@/core/runtime/config", () => ({
  useRuntimeManager: () => ({
    getAiURL: () => new URL("http://localhost/api/completion"),
    headers: () => ({}),
  }),
}));
vi.mock("@/core/codemirror/utils", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/core/codemirror/utils")>()),
  selectAllText: vi.fn(),
}));
vi.mock("@/core/ai/staged-cells", () => ({ useStagedAICell: () => undefined }));
vi.mock("@/theme/useTheme", () => ({ useTheme: () => ({ theme: "light" }) }));
vi.mock("@/components/ai/ai-model-dropdown", () => ({
  AIModelDropdown: () => null,
}));
vi.mock("@/components/chat/chat-components", () => ({
  AddContextButton: () => null,
  SendButton: () => null,
}));
vi.mock("../completion-handlers", async (importOriginal) => {
  const original =
    await importOriginal<typeof import("../completion-handlers")>();
  return {
    ...original,
    AcceptCompletionButton: () => null,
    RejectCompletionButton: ({ onDecline }: { onDecline: () => void }) => (
      <button type="button" onClick={onDecline}>
        Revert change
      </button>
    ),
  };
});
vi.mock("../add-cell-with-ai", () => ({
  PromptInput: ({
    inputRef,
  }: {
    inputRef: { current: { view: { focus: () => void } } | null };
  }) => (
    <textarea
      aria-label="AI prompt"
      ref={(element) => {
        inputRef.current = element
          ? {
              view: {
                focus: () => {
                  // Match browsers refusing focus while an ancestor is visibility:hidden.
                  if (!element.closest(".invisible")) {
                    element.focus();
                  }
                },
              },
            }
          : null;
      }}
    />
  ),
}));

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("AI completion prompt focus", () => {
  it("focuses the prompt after rejection makes it visible, including repeated rejection", () => {
    vi.useFakeTimers();
    const cellId = CellId.create();
    render(
      <TooltipProvider>
        <AiCompletionEditor
          cellId={cellId}
          aiCompletionCell={{
            cellId,
            initialPrompt: "Fix this",
            triggerImmediately: true,
          }}
          currentCode="x = 1"
          currentLanguageAdapter="python"
          onChange={vi.fn()}
          acceptChange={vi.fn()}
          declineChange={vi.fn()}
          runCell={vi.fn()}
        >
          <textarea aria-label="Cell code" />
        </AiCompletionEditor>
      </TooltipProvider>,
    );

    const prompt = screen.getByLabelText("AI prompt");
    expect(prompt.closest(".invisible")).not.toBeNull();
    const reject = screen.getByRole("button", { name: "Revert change" });
    reject.focus();
    fireEvent.click(reject);
    act(() => vi.advanceTimersByTime(20));
    expect(prompt.closest(".invisible")).toBeNull();
    expect(prompt).toHaveFocus();

    reject.focus();
    fireEvent.click(reject);
    act(() => vi.advanceTimersByTime(20));
    expect(prompt).toHaveFocus();
  });
});
