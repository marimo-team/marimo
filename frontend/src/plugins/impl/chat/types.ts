/* Copyright 2024 Marimo. All rights reserved. */
export type ChatRole = "system" | "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  content: string;
  attachments?: ChatAttachment[];
}

export interface ChatAttachment {
  name?: string;
  contentType?: string;
  url: string;
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

export interface ChatConfig {
  maxTokens: number;
  temperature: number;
  topP: number;
  topK: number;
  frequencyPenalty: number;
  presencePenalty: number;
}
