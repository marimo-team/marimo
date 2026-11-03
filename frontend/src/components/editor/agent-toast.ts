/* Copyright 2026 Marimo. All rights reserved. */

import { toast } from "@/components/ui/use-toast";
import type { SendResult } from "@/core/agents/messages";

type AgentToastOptions = Pick<
  Parameters<typeof toast>[0],
  "title" | "variant" | "description"
>;

export function agentToast(options: AgentToastOptions) {
  const duration = options.variant === "danger" ? 5000 : 3000;
  const { dismiss } = toast({ ...options, duration });
  // Agent notices must also expire while the user focuses the agent terminal.
  window.setTimeout(dismiss, duration);
}

export function formatAgentSendResult(
  result: SendResult,
  labels: ReadonlyMap<string, string>,
): AgentToastOptions {
  const label = (id: string) => labels.get(id) ?? id;
  const submitted = result.recipients.filter((r) => r.status === "submitted");
  if (submitted.length === result.recipients.length) {
    return {
      title: `Submitted to ${submitted.map((r) => label(r.agent_id)).join(", ")}`,
    };
  }
  const uncertain = result.recipients.some((r) => r.status === "unknown");
  let title = "Message rejected";
  if (submitted.length > 0) {
    title = "Some messages were not confirmed";
  } else if (uncertain) {
    title = "Submission outcome unknown";
  }
  return {
    variant: "danger",
    title,
    description:
      result.recipients
        .map((r) => `${label(r.agent_id)}: ${r.detail ?? r.status}`)
        .join("\n") +
      (uncertain ? "\nAnother send can duplicate the message." : ""),
  };
}
