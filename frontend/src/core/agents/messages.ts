/* Copyright 2026 Marimo. All rights reserved. */

import type { StableSessionId } from "@/core/kernel/session";
import { API } from "@/core/network/api";

/** One agent by its Agent ID, or every connected agent. */
export type AgentRecipient = { to: string } | { broadcast: true };

type MessageRequest = AgentRecipient & {
  message_id: string;
  message: unknown;
  sender?: string;
};

export interface RecipientResult {
  agent_id: string;
  name: string | null;
  status: "submitted" | "unknown" | "rejected";
  reason: string | null;
  detail: string | null;
}

export interface SendResult {
  message_id: string;
  recipients: RecipientResult[];
}

export function sendAgentMessage(
  sessionId: StableSessionId,
  message: unknown,
  recipient: AgentRecipient,
  sender?: string,
): Promise<SendResult> {
  return API.post<MessageRequest, SendResult>(
    `/pair/notebooks/${encodeURIComponent(sessionId)}/messages`,
    { message_id: crypto.randomUUID(), message, ...recipient, sender },
  );
}
