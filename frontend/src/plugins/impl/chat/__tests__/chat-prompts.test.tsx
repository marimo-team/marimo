/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import type { PopoverContent } from "@/components/ui/popover";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Chatbot } from "../chat-ui";

vi.mock("@/components/editor/ai/add-cell-with-ai", () => ({
  PromptInput: ({ value }: { value: string }) => (
    <textarea aria-label="Chat prompt" value={value} readOnly={true} />
  ),
}));

vi.mock("@/components/ui/popover", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/components/ui/popover")>();
  return {
    ...actual,
    // Keep the form mounted when the prompt menu takes focus so this tests
    // the prompt reset rather than the overlay's incidental unmount.
    PopoverContent: (props: ComponentProps<typeof PopoverContent>) => (
      <actual.PopoverContent
        {...props}
        onInteractOutside={(event) => event.preventDefault()}
      />
    ),
  };
});

describe("chat prompt variables", () => {
  const originalScrollTo = HTMLElement.prototype.scrollTo;
  beforeAll(() => {
    HTMLElement.prototype.scrollTo = vi.fn();
  });
  afterAll(() => {
    HTMLElement.prototype.scrollTo = originalScrollTo;
  });

  it("clears entered values and replaces the fields when selecting another prompt", async () => {
    const firstPrompt = "Tell {{name}} about {{topic}}";
    const secondPrompt = "Send {{name}} to {{destination}}";
    render(
      <TooltipProvider>
        <Chatbot
          prompts={[firstPrompt, secondPrompt]}
          config={{
            max_tokens: null,
            temperature: null,
            top_p: null,
            top_k: null,
            frequency_penalty: null,
            presence_penalty: null,
          }}
          showConfigurationControls={false}
          maxHeight={undefined}
          allowAttachments={false}
          disabled={false}
          value={[]}
          setValue={vi.fn()}
          host={document.createElement("div")}
          get_chat_history={vi.fn().mockResolvedValue({ messages: [] })}
          delete_chat_history={vi.fn().mockResolvedValue(null)}
          delete_chat_message={vi.fn().mockResolvedValue(null)}
          send_prompt={vi.fn().mockResolvedValue(null)}
          cancel_prompt={vi.fn().mockResolvedValue(null)}
        />
      </TooltipProvider>,
    );

    const promptMenu = screen.getByRole("button", { expanded: false });
    fireEvent.keyDown(promptMenu, { key: "ArrowDown" });
    fireEvent.click(await screen.findByRole("menuitem", { name: firstPrompt }));
    fireEvent.change(await screen.findByLabelText("name"), {
      target: { value: "Ada" },
    });
    fireEvent.change(screen.getByLabelText("topic"), {
      target: { value: "Python" },
    });
    expect(screen.getByRole("button", { name: "Submit" })).toBeEnabled();

    fireEvent.keyDown(promptMenu, { key: "ArrowDown" });
    fireEvent.click(
      await screen.findByRole("menuitem", { name: secondPrompt }),
    );

    expect(await screen.findByLabelText("destination")).toHaveValue("");
    expect(screen.getByLabelText("name")).toHaveValue("");
    expect(screen.queryByLabelText("topic")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
  });
});
