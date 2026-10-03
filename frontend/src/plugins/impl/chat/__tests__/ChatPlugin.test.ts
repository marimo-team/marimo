/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { ChatPlugin } from "../ChatPlugin";
import type { ChatConfig, ChatMessage, SendMessageRequest } from "../types";

const config: ChatConfig = {
  max_tokens: null,
  temperature: null,
  top_p: null,
  top_k: null,
  frequency_penalty: null,
  presence_penalty: null,
};

describe("ChatPlugin message validation", () => {
  const functions = ChatPlugin.functions;
  if (!functions) {
    throw new Error("ChatPlugin must define its RPC functions");
  }

  const message: ChatMessage = {
    id: "user-message",
    role: "user",
    content: "Hello",
    parts: [{ type: "text", text: "Hello" }],
  };

  describe.each([
    { name: "omitted", message },
    { name: "null", message: { ...message, metadata: null } },
    {
      name: "populated",
      message: { ...message, metadata: { source: "notebook" } },
    },
  ])("with $name metadata", ({ message }) => {
    it("accepts the message when sending a prompt", () => {
      const request: SendMessageRequest = {
        request_id: "request-id",
        messages: [message],
        config,
      };

      expect(functions.send_prompt.input.parse(request)).toEqual(request);
    });

    it("accepts the message in chat history", () => {
      const response = { messages: [message] };

      expect(functions.get_chat_history.output.parse(response)).toEqual(
        response,
      );
    });
  });
});
