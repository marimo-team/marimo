/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import type { ToolUIPart, UIMessage } from "ai";
import { describe, expect, it, vi } from "vitest";
import { renderUIMessage } from "../chat-display";

vi.mock("../tool-call/tool-call-view", () => ({
  ToolCallView: ({ toolName }: { toolName: string }) => <div>{toolName}</div>,
}));
vi.mock("../../markdown/markdown-renderer", () => ({
  MarkdownRenderer: ({ content }: { content: string }) => <p>{content}</p>,
}));

const tool = (
  name = "edit_notebook_tool",
  state: ToolUIPart["state"] = "output-available",
): ToolUIPart =>
  ({
    type: `tool-${name}`,
    toolCallId: crypto.randomUUID(),
    state,
    input: {},
    output: {},
    approval: state === "approval-requested" ? { id: "approval" } : undefined,
  }) as ToolUIPart;

const reasoning = (text: string): UIMessage["parts"][number] => ({
  type: "reasoning",
  text,
  state: "done",
});

function show(
  parts: UIMessage["parts"],
  {
    isActive = false,
    metadata,
  }: { isActive?: boolean; metadata?: Record<string, number | boolean> } = {},
) {
  return render(
    <div>
      {renderUIMessage({
        message: { id: "message", role: "assistant", parts, metadata },
        isLast: true,
        isActive,
      })}
    </div>,
  );
}

describe("assistant turn rendering", () => {
  it("folds interleaved reasoning, narration, and tools into one block above the answer", () => {
    show([
      reasoning("Plan the cells"),
      tool("get_lightweight_cell_map"),
      { type: "step-start" },
      { type: "text", text: "Adding the function now." },
      reasoning("Write fib"),
      tool(),
      { type: "text", text: "Added `fib`." },
    ]);

    const summary = screen.getByRole("button", {
      name: "Worked through 2 steps",
    });
    expect(summary.getAttribute("aria-expanded")).toBe("false");
    expect(screen.getByText("Added `fib`.")).toBeTruthy();
    expect(screen.queryByText("Plan the cells")).toBeNull();

    fireEvent.click(summary);
    expect(screen.getByText("Plan the cells")).toBeTruthy();
    expect(screen.getByText("Adding the function now.")).toBeTruthy();
    expect(screen.getByText("tool-get_lightweight_cell_map")).toBeTruthy();
    expect(screen.getByText("tool-edit_notebook_tool")).toBeTruthy();
  });

  it("reports how long the turn took", () => {
    const view = show([tool(), { type: "text", text: "Done." }], {
      metadata: { startedAt: 0, finishedAt: 65_000 },
    });
    expect(
      screen.getByRole("button", { name: "Worked for 1m 5s" }),
    ).toBeTruthy();
    view.unmount();

    show([reasoning("Hmm"), { type: "text", text: "Hi." }], {
      metadata: { startedAt: 0, finishedAt: 8_000 },
    });
    expect(screen.getByRole("button", { name: "Thought for 8s" })).toBeTruthy();
  });

  it("stays open while running and collapses once the answer is in", () => {
    const parts: UIMessage["parts"] = [
      reasoning("Plan"),
      tool("edit_notebook_tool", "input-available"),
    ];
    const view = show(parts, { isActive: true });
    expect(screen.getByRole("status").textContent).toBe("Working…");
    expect(screen.getByText("tool-edit_notebook_tool")).toBeTruthy();

    view.rerender(
      <div>
        {renderUIMessage({
          message: {
            id: "message",
            role: "assistant",
            parts: [
              ...parts.slice(0, 1),
              tool(),
              { type: "text", text: "Done." },
            ],
          },
          isLast: true,
          isActive: false,
        })}
      </div>,
    );
    const summary = screen.getByRole("button", {
      name: "Worked through 1 step",
    });
    expect(summary.getAttribute("aria-expanded")).toBe("false");
  });

  it("leaves a stopped turn open since there is no answer to read", () => {
    show([reasoning("Plan"), tool("edit_notebook_tool", "input-available")]);
    const summary = screen.getByRole("button", { name: "Stopped" });
    expect(summary.getAttribute("aria-expanded")).toBe("true");
  });

  it("labels a stopped turn even without pending tools", () => {
    show([reasoning("Plan"), { type: "text", text: "Partial" }], {
      metadata: { startedAt: 0, finishedAt: 3_000, stopped: true },
    });
    expect(
      screen.getByRole("button", { name: "Stopped after 3s" }),
    ).toBeTruthy();
  });

  it("flags failed steps in the summary", () => {
    show([
      tool("lint_notebook", "output-error"),
      { type: "text", text: "Hm." },
    ]);
    expect(screen.getByRole("button", { name: /1 failed/ })).toBeTruthy();
  });

  it("shows a thinking indicator before any content arrives", () => {
    show([reasoning("")], { isActive: true });
    expect(screen.getByRole("status").textContent).toBe("Thinking…");
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("keeps pending approvals, and the text explaining them, outside the block", () => {
    show([
      reasoning("Needs approval"),
      { type: "text", text: "I'll run a query." },
      tool("run_query", "approval-requested"),
    ]);
    expect(screen.getByText("I'll run a query.")).toBeTruthy();
    expect(screen.getByText("tool-run_query")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Thought process" }),
    ).toBeTruthy();
  });

  it("renders plain answers without an activity block", () => {
    show([{ type: "text", text: "Hello!" }]);
    expect(screen.getByText("Hello!")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });
});
