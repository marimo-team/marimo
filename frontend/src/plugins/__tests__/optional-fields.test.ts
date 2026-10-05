/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { invariant } from "@/utils/invariant";
import { ChatPlugin } from "../impl/chat/ChatPlugin";
import { FormPlugin } from "../impl/FormPlugin";
import { PanelPlugin } from "../impl/panel/PanelPlugin";
import { JsonOutputPlugin } from "../layout/JsonOutputPlugin";

const chatFunctions = ChatPlugin.functions;
const formFunctions = FormPlugin.functions;
const panelFunctions = PanelPlugin.functions;
invariant(chatFunctions, "Chat RPC schemas must be defined");
invariant(formFunctions, "Form RPC schemas must be defined");
invariant(panelFunctions, "Panel RPC schemas must be defined");

describe("chat message metadata", () => {
  const message = {
    id: "message-1",
    role: "user",
    content: "Hello",
    parts: [{ type: "text", text: "Hello" }],
  };
  const config = {
    max_tokens: null,
    temperature: null,
    top_p: null,
    top_k: null,
    frequency_penalty: null,
    presence_penalty: null,
  };

  it.each([{}, { metadata: null }, { metadata: { source: "user" } }])(
    "accepts metadata %j in prompts and history",
    (metadata) => {
      const messages = [{ ...message, ...metadata }];
      const prompt = { request_id: "request-1", messages, config };

      expect(chatFunctions.send_prompt.input.parse(prompt)).toEqual(prompt);
      expect(chatFunctions.get_chat_history.output.parse({ messages })).toEqual(
        { messages },
      );
    },
  );

  it("still rejects invalid message roles", () => {
    expect(
      chatFunctions.get_chat_history.output.safeParse({
        messages: [{ ...message, role: "invalid" }],
      }).success,
    ).toBe(false);
  });
});

describe("required plugin payloads", () => {
  it.each([{ value: undefined }, { value: null }, { value: 0 }])(
    "accepts form validation input %j",
    (input) => {
      expect(formFunctions.validate.input.parse(input)).toEqual(input);
    },
  );

  it.each([{ jsonData: null }, { jsonData: { count: 0 } }])(
    "accepts JSON output data %j",
    (data) => {
      expect(new JsonOutputPlugin().validator.parse(data)).toEqual({
        ...data,
        valueTypes: "python",
      });
    },
  );

  it("requires the form and JSON output payload keys", () => {
    expect(formFunctions.validate.input.safeParse({}).success).toBe(false);
    expect(new JsonOutputPlugin().validator.safeParse({}).success).toBe(false);
  });

  it("requires a Panel message to match the Python RPC arguments", () => {
    expect(
      panelFunctions.send_to_widget.input.safeParse({ buffers: [] }).success,
    ).toBe(false);

    const input = { message: { type: "PATCH-DOC" }, buffers: [] };
    expect(panelFunctions.send_to_widget.input.parse(input)).toEqual(input);
  });
});
