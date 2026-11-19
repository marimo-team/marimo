/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { ChevronDownIcon, SendIcon } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  type AgentRecipient,
  type RecipientResult,
  sendAgentMessage,
} from "@/core/agents/messages";
import { attachmentLabel, useNotebookAttachments } from "@/core/notebook";
import { agentToast } from "@/components/editor/agent-toast";
import { pairConfigAtom } from "@/core/config/pair";
import { stableSessionIdAtom } from "@/core/kernel/session";
import { uniqueByTakeLast } from "@/utils/arrays";
import { prettyError } from "@/utils/errors";

function formatOutcome(
  recipient: RecipientResult,
  labels: Map<string, string>,
) {
  const name =
    labels.get(recipient.agent_id) ?? recipient.name ?? recipient.agent_id;
  let title: string;
  if (recipient.status === "submitted") {
    title = `Submitted to ${name}`;
  } else if (
    recipient.status === "unknown" &&
    recipient.reason === "unconfirmed"
  ) {
    title = `Sent to ${name}; acceptance unconfirmed`;
  } else {
    title = `${name}: ${recipient.status} (${recipient.reason})`;
  }
  return { title, detail: recipient.detail };
}

export function SendErrorReportButton({
  getContent,
}: {
  getContent: () => unknown;
}) {
  const hostEnabled = useAtomValue(pairConfigAtom)?.hostEnabled;
  const attachments = useNotebookAttachments("agent");
  const stableSessionId = useAtomValue(stableSessionIdAtom);
  const [sending, setSending] = useState(false);

  // One agent can hold several attachments. The server addresses an agent by
  // its identity, so the choices here are identities, not attachments.
  const agents = uniqueByTakeLast(
    attachments.map((attachment) => ({
      id: attachment.identity || attachment.id,
      name: attachmentLabel(attachment),
    })),
    (agent) => agent.id,
  );
  // Agents of the same harness share a name. The end of the Agent ID tells
  // them apart.
  const labels = new Map(
    agents.map((agent) => [
      agent.id,
      agents.some((other) => other.id !== agent.id && other.name === agent.name)
        ? `${agent.name} (${agent.id.slice(-6)})`
        : agent.name,
    ]),
  );

  if (!hostEnabled || agents.length === 0) {
    return null;
  }

  const send = async (recipient: AgentRecipient) => {
    if (sending || !stableSessionId) {
      return;
    }
    setSending(true);
    try {
      const result = await sendAgentMessage(
        stableSessionId,
        getContent(),
        recipient,
        "marimo error report",
      );
      const outcomes = result.recipients.map((outcome) =>
        formatOutcome(outcome, labels),
      );
      if (outcomes.length === 1) {
        const outcome = outcomes[0];
        agentToast({
          title: outcome.title,
          ...(outcome.detail ? { description: outcome.detail } : {}),
        });
      } else if (outcomes.length > 1) {
        agentToast({
          title: "Agent message outcomes",
          description: outcomes
            .map(({ title, detail }) =>
              detail ? `${title}: ${detail}` : title,
            )
            .join("\n"),
        });
      }
    } catch (error) {
      agentToast({
        variant: "danger",
        title: "Could not send error",
        description: prettyError(error),
      });
    } finally {
      setSending(false);
    }
  };

  const disabled = sending || !stableSessionId;
  const label = (
    <>
      <SendIcon className="h-3 w-3 mr-2" />
      Send error to agent
    </>
  );

  if (agents.length === 1) {
    return (
      <Button
        size="xs"
        variant="outline"
        disabled={disabled}
        onClick={() => send({ broadcast: true })}
      >
        {label}
      </Button>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild={true}>
        <Button size="xs" variant="outline" disabled={disabled}>
          {label}
          <ChevronDownIcon className="h-3 w-3 ml-2" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        {agents.map((agent) => (
          <DropdownMenuItem
            key={agent.id}
            onSelect={() => send({ to: agent.id })}
          >
            {labels.get(agent.id)}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => send({ broadcast: true })}>
          Send to all agents
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
