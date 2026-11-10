/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { act, render, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Toaster } from "@/components/ui/toaster";
import { clearToasts, toast, useToast } from "@/components/ui/use-toast";
import type { SendResult } from "@/core/agents/messages";
import { agentToast, formatAgentSendResult } from "../agent-toast";

describe("agent notifications", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    clearToasts();
  });

  afterEach(() => {
    act(() => {
      clearToasts();
      vi.runOnlyPendingTimers();
    });
    vi.useRealTimers();
  });

  it.each([
    { variant: undefined, duration: 3000 },
    { variant: "danger" as const, duration: 5000 },
  ])("expires while the window is blurred: %j", ({ variant, duration }) => {
    const { result } = renderHook(useToast);
    render(<Toaster />);
    act(() => agentToast({ title: "Agent notice", variant }));
    act(() => window.dispatchEvent(new Event("blur")));
    act(() => vi.advanceTimersByTime(duration - 1));
    expect(result.current.toasts[0].open).toBe(true);
    act(() => vi.advanceTimersByTime(1));
    expect(result.current.toasts[0].open).toBe(false);
  });

  it("preserves pause behavior for ordinary notifications", () => {
    const { result } = renderHook(useToast);
    render(<Toaster />);
    act(() => toast({ title: "Ordinary notice", duration: 3000 }));
    act(() => window.dispatchEvent(new Event("blur")));
    act(() => vi.advanceTimersByTime(5000));
    expect(result.current.toasts[0].open).toBe(true);
  });

  it("does not let an older timer dismiss a newer notification", () => {
    const { result } = renderHook(useToast);
    act(() => agentToast({ title: "First" }));
    act(() => vi.advanceTimersByTime(1000));
    act(() => agentToast({ title: "Second" }));
    act(() => vi.advanceTimersByTime(2000));
    expect(result.current.toasts[0].title).toBe("Second");
    expect(result.current.toasts[0].open).toBe(true);
    act(() => vi.advanceTimersByTime(1000));
    expect(result.current.toasts[0].open).toBe(false);
  });
});

describe("agent send result formatting", () => {
  it.each<{
    name: string;
    recipients: SendResult["recipients"];
    expected: Parameters<typeof agentToast>[0];
  }>([
    {
      name: "all submitted",
      recipients: [
        { agent_id: "pi", status: "submitted", detail: null },
        { agent_id: "claude", status: "submitted", detail: null },
      ],
      expected: { title: "Submitted to Pi, Claude" },
    },
    {
      name: "rejected",
      recipients: [
        { agent_id: "pi", status: "rejected", detail: "Disconnected" },
      ],
      expected: {
        variant: "danger",
        title: "Message rejected",
        description: "Pi: Disconnected",
      },
    },
    {
      name: "unknown with a missing label and detail",
      recipients: [{ agent_id: "unlabeled", status: "unknown", detail: null }],
      expected: {
        variant: "danger",
        title: "Submission outcome unknown",
        description:
          "unlabeled: unknown\nAnother send can duplicate the message.",
      },
    },
    {
      name: "partially rejected",
      recipients: [
        { agent_id: "pi", status: "submitted", detail: null },
        { agent_id: "claude", status: "rejected", detail: null },
      ],
      expected: {
        variant: "danger",
        title: "Some messages were not confirmed",
        description: "Pi: submitted\nClaude: rejected",
      },
    },
    {
      name: "partially unknown",
      recipients: [
        { agent_id: "pi", status: "submitted", detail: null },
        { agent_id: "claude", status: "unknown", detail: "No receipt" },
      ],
      expected: {
        variant: "danger",
        title: "Some messages were not confirmed",
        description:
          "Pi: submitted\nClaude: No receipt\nAnother send can duplicate the message.",
      },
    },
    {
      name: "rejected and unknown",
      recipients: [
        { agent_id: "pi", status: "rejected", detail: null },
        { agent_id: "claude", status: "unknown", detail: null },
      ],
      expected: {
        variant: "danger",
        title: "Submission outcome unknown",
        description:
          "Pi: rejected\nClaude: unknown\nAnother send can duplicate the message.",
      },
    },
  ])("formats $name", ({ recipients, expected }) => {
    const labels = new Map([
      ["pi", "Pi"],
      ["claude", "Claude"],
    ]);
    expect(formatAgentSendResult({ recipients }, labels)).toEqual(expected);
  });
});
