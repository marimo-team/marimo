/* Copyright 2026 Marimo. All rights reserved. */

import { z } from "zod";
import type { StableSessionId } from "@/core/kernel/session";
import { API } from "@/core/network/api";
import { HTTPError } from "@/utils/errors";

const sendResultSchema = z.object({
  recipients: z
    .array(
      z.object({
        agent_id: z.string(),
        status: z.enum(["submitted", "rejected", "unknown"]),
        detail: z.string().nullable(),
      }),
    )
    .min(1),
});

const messageErrorSchema = z.object({
  code: z.enum(["unavailable", "no-agents", "invalid-argument", "failed"]),
  detail: z.string(),
});

export type SendResult = z.infer<typeof sendResultSchema>;
export type AgentRecipient = { to: string } | { broadcast: true };

export class SendOutcomeUnknownError extends Error {
  public constructor() {
    super(
      "The submission outcome is unknown. Another send can duplicate the message.",
    );
  }
}

export async function sendAgentMessage(
  sessionId: StableSessionId,
  message: unknown,
  recipient: AgentRecipient,
): Promise<SendResult> {
  const content = z.json().parse(message);
  try {
    const result = await API.post<unknown, unknown>(
      `/pair/notebooks/${encodeURIComponent(sessionId)}/messages`,
      { message: content, ...recipient },
      { signal: AbortSignal.timeout(30_000) },
    );
    return sendResultSchema.parse(result);
  } catch (error) {
    if (
      error instanceof HTTPError &&
      ([401, 403, 404, 405].includes(error.status) ||
        ([400, 409, 503].includes(error.status) &&
          messageErrorSchema.safeParse(error.cause).success))
    ) {
      throw error;
    }
    throw new SendOutcomeUnknownError();
  }
}
