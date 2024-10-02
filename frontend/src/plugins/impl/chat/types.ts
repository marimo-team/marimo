/* Copyright 2024 Marimo. All rights reserved. */
export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
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
