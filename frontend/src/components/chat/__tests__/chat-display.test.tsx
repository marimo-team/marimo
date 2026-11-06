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

const done = (name = "edit_notebook_tool"): ToolUIPart => ({
  type: `tool-${name}`,
  toolCallId: crypto.randomUUID(),
  state: "output-available",
  input: {},
  output: {},
});

function show(parts: UIMessage["parts"], isActive = false) {
  return render(
    renderUIMessage({
      message: { id: "message", role: "assistant", parts },
      isStreamingReasoning: false,
      isLast: true,
      isActive,
    }),
  );
}

describe("chat tool activity", () => {
  it("collapses consecutive edits across SDK step boundaries and exposes details on demand", () => {
    show([done(), { type: "step-start" }, done(), done(), done()]);
    const summary = screen.getByRole("button", {
      name: "Edited notebook · 4 operations",
    });
    expect(summary.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText("tool-edit_notebook_tool")).toBeNull();
    fireEvent.click(summary);
    expect(screen.getAllByText("tool-edit_notebook_tool")).toHaveLength(4);
  });

  it("starts a new group after prose and summarizes mixed tool calls", () => {
    show([
      done(),
      { type: "text", text: "Checking the result." },
      done("lint_notebook"),
      {
        type: "dynamic-tool",
        toolName: "get_lightweight_cell_map",
        toolCallId: "dynamic",
        state: "output-available",
        input: {},
        output: {},
      },
    ]);
    expect(screen.getByText("Checking the result.")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Edited notebook · 1 operation" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Completed 2 steps" }),
    ).toBeTruthy();
  });

  it("keeps errors, denials, and approval requests outside collapsed groups", () => {
    show([
      done(),
      {
        type: "tool-failed",
        toolCallId: "error",
        state: "output-error",
        input: {},
        errorText: "Failed",
      },
      {
        type: "tool-approval",
        toolCallId: "approval",
        state: "approval-requested",
        input: {},
        approval: { id: "approval" },
      },
      {
        type: "tool-denied",
        toolCallId: "denied",
        state: "output-denied",
        input: {},
        approval: { id: "denied", approved: false },
      },
      done(),
    ]);
    expect(screen.getByText("tool-failed")).toBeTruthy();
    expect(screen.getByText("tool-approval")).toBeTruthy();
    expect(screen.getByText("tool-denied")).toBeTruthy();
    expect(
      screen.getAllByRole("button", { name: "Edited notebook · 1 operation" }),
    ).toHaveLength(2);
  });

  it("distinguishes running edits from interrupted activity", () => {
    const parts: UIMessage["parts"] = [
      done(),
      {
        type: "tool-edit_notebook_tool",
        toolCallId: "pending",
        state: "input-available",
        input: {},
      },
    ];
    const view = show(parts, true);
    expect(
      screen.getByRole("button", { name: "Editing notebook…" }),
    ).toBeTruthy();
    view.unmount();
    show(parts);
    expect(
      screen.getByRole("button", {
        name: "Stopped before completing all steps",
      }),
    ).toBeTruthy();
  });
});
