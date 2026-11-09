/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { describe, expect, it, vi } from "vitest";
import { FRONTEND_TOOL_REGISTRY } from "@/core/ai/tools/registry";
import { handleToolCall } from "../chat-utils";

describe("handleToolCall", () => {
  it.each([
    {
      input: { query: "select 1", limit: 5 },
      args: { query: "select 1", limit: 5 },
    },
    { input: null, args: {} },
    { input: undefined, args: {} },
  ])("validates backend tool arguments ($input)", async ({ input, args }) => {
    const hasTool = vi
      .spyOn(FRONTEND_TOOL_REGISTRY, "has")
      .mockReturnValue(false);
    const invokeAiTool = vi.fn().mockResolvedValue({ result: "done" });
    const addToolOutput = vi.fn();
    try {
      await handleToolCall({
        invokeAiTool,
        addToolOutput,
        toolCall: { toolName: "query", toolCallId: "call-1", input },
        toolContext: {
          store: createStore(),
          addStagedCell: vi.fn(),
          createCell: vi.fn(),
        },
      });
      expect(invokeAiTool).toHaveBeenCalledExactlyOnceWith({
        toolName: "query",
        arguments: args,
      });
      expect(addToolOutput).toHaveBeenCalledExactlyOnceWith({
        tool: "query",
        toolCallId: "call-1",
        output: "done",
      });
    } finally {
      hasTool.mockRestore();
    }
  });

  it.each(["invalid", 42, true, ["invalid"]])(
    "rejects non-object backend arguments (%s)",
    async (input) => {
      const hasTool = vi
        .spyOn(FRONTEND_TOOL_REGISTRY, "has")
        .mockReturnValue(false);
      const invokeAiTool = vi.fn();
      const addToolOutput = vi.fn();
      try {
        await handleToolCall({
          invokeAiTool,
          addToolOutput,
          toolCall: { toolName: "query", toolCallId: "call-1", input },
          toolContext: {
            store: createStore(),
            addStagedCell: vi.fn(),
            createCell: vi.fn(),
          },
        });
        expect(invokeAiTool).not.toHaveBeenCalled();
        expect(addToolOutput).toHaveBeenCalledExactlyOnceWith({
          tool: "query",
          toolCallId: "call-1",
          state: "output-error",
          errorText: expect.any(String),
        });
      } finally {
        hasTool.mockRestore();
      }
    },
  );

  it.each(["frontend", "backend", "exception"])(
    "reports %s failures as errors rather than successful output",
    async (source) => {
      const hasTool = vi
        .spyOn(FRONTEND_TOOL_REGISTRY, "has")
        .mockReturnValue(source === "frontend");
      const response = {
        tool_name: "test_tool",
        result: null,
        error: "Edit failed",
      };
      const invokeFrontend = vi
        .spyOn(FRONTEND_TOOL_REGISTRY, "invoke")
        .mockResolvedValue(response);
      const invokeAiTool = vi.fn().mockImplementation(async () => {
        if (source === "exception") {
          throw new Error("Edit failed");
        }
        return response;
      });
      const addToolOutput = vi.fn();
      try {
        await handleToolCall({
          invokeAiTool,
          addToolOutput,
          toolCall: { toolName: "test_tool", toolCallId: "call-1", input: {} },
          toolContext: {
            store: createStore(),
            addStagedCell: vi.fn(),
            createCell: vi.fn(),
          },
        });
        expect(addToolOutput).toHaveBeenCalledExactlyOnceWith({
          tool: "test_tool",
          toolCallId: "call-1",
          state: "output-error",
          errorText: "Edit failed",
        });
      } finally {
        hasTool.mockRestore();
        invokeFrontend.mockRestore();
      }
    },
  );
});
