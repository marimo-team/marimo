/* Copyright 2026 Marimo. All rights reserved. */

import type { UIMessage } from "ai";

export type ChatRole = "system" | "user" | "assistant";

export interface ChatMessage extends UIMessage {
  content: string | null; // Content is only added for backwards compatibility
}

/**
 * These are snake_case because they come from the backend,
 * and are not modified when sent to the frontend.
 */
export interface ChatConfig {
  max_tokens: number | null;
  temperature: number | null;
  top_p: number | null;
  top_k: number | null;
  frequency_penalty: number | null;
  presence_penalty: number | null;
}

export interface SendMessageRequest {
  messages: ChatMessage[];
  config: ChatConfig;
}
