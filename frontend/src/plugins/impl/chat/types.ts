/* Copyright 2024 Marimo. All rights reserved. */

import type { UIMessage } from "ai";

export type ChatRole = "system" | "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  content: string; // TODO: Deprecate content
  parts: UIMessage["parts"];
}

export interface SendMessageRequest {
  messages: ChatMessage[];
  config: {
    max_tokens?: number;
    temperature?: number;
    top_p?: number;
    top_k?: number;
    frequency_penalty?: number;
    presence_penalty?: number;
  };
}

/**
 * These are snake_case because they come from the backend,
 * and are not modified when sent to the frontend.
 */
export interface ChatConfig {
  max_tokens: number;
  temperature: number;
  top_p: number;
  top_k: number;
  frequency_penalty: number;
  presence_penalty: number;
}
