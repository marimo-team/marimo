/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { SendIcon } from "lucide-react";
import { useRef, useState } from "react";
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
  sendAgentMessage,
  SendOutcomeUnknownError,
} from "@/core/agents/messages";
import { connectedAgentsAtom } from "@/core/agents/state";
import { agentToast } from "@/components/editor/agent-toast";
import { stableSessionIdAtom } from "@/core/kernel/session";
import { initialModeAtom } from "@/core/mode";
import { prettyError } from "@/utils/errors";

export function SendToAgentButton({
  getContent,
  children,
}: {
  getContent: () => unknown;
  children: React.ReactNode;
}) {
  const isEditMode = useAtomValue(initialModeAtom) === "edit";
  const agents = useAtomValue(connectedAgentsAtom);
  const sessionId = useAtomValue(stableSessionIdAtom);
  const [sending, setSending] = useState(false);
  const pending = useRef(false);

  if (!isEditMode || agents.length === 0) {
    return null;
  }

  const send = async (recipient: AgentRecipient) => {
    if (pending.current || !sessionId) {
      return;
    }
    pending.current = true;
    setSending(true);
    const selected = new Map(agents.map((agent) => [agent.id, agent.name]));
    try {
      const result = await sendAgentMessage(sessionId, getContent(), recipient);
      const submitted = result.recipients.filter(
        (r) => r.status === "submitted",
      );
      const uncertain = result.recipients.some((r) => r.status === "unknown");
      if (submitted.length === result.recipients.length) {
        agentToast({
          title: `Submitted to ${submitted.map((r) => selected.get(r.agent_id) ?? r.agent_id).join(", ")}`,
        });
      } else {
        agentToast({
          variant: "danger",
          title:
            submitted.length > 0
              ? "Some messages were not confirmed"
              : uncertain
                ? "Submission outcome unknown"
                : "Message rejected",
          description:
            result.recipients
              .map(
                (r) =>
                  `${selected.get(r.agent_id) ?? r.agent_id}: ${r.detail ?? r.status}`,
              )
              .join("\n") +
            (uncertain ? "\nAnother send can duplicate the message." : ""),
        });
      }
    } catch (error) {
      agentToast({
        variant: "danger",
        title:
          error instanceof SendOutcomeUnknownError
            ? "Submission outcome unknown"
            : "Could not send message",
        description: prettyError(error),
      });
    } finally {
      pending.current = false;
      setSending(false);
    }
  };

  const button = (
    <Button
      size="xs"
      variant="outline"
      disabled={sending || !sessionId}
      onClick={
        agents.length === 1 ? () => send({ to: agents[0].id }) : undefined
      }
    >
      <SendIcon className="h-3 w-3 mr-2" />
      {children}
    </Button>
  );

  if (agents.length === 1) {
    return button;
  }
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild={true}>{button}</DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        {agents.map((agent) => (
          <DropdownMenuItem
            key={agent.id}
            onSelect={() => send({ to: agent.id })}
          >
            {agents.filter((a) => a.name === agent.name).length > 1
              ? `${agent.name} (${agent.id})`
              : agent.name}
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
