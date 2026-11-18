/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { SendIcon } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { type RecipientResult, sendAgentMessage } from "@/core/agents/messages";
import { useNotebookAttachments } from "@/core/notebook";
import { agentToast } from "@/components/editor/agent-toast";
import { pairConfigAtom } from "@/core/config/pair";
import { stableSessionIdAtom } from "@/core/kernel/session";
import { prettyError } from "@/utils/errors";

function formatOutcome(recipient: RecipientResult) {
  const name = recipient.name ?? recipient.agent_id;
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
  const agents = useNotebookAttachments("agent");
  const stableSessionId = useAtomValue(stableSessionIdAtom);
  const [sending, setSending] = useState(false);

  if (!hostEnabled || agents.length === 0) {
    return null;
  }

  const send = async () => {
    if (sending || agents.length === 0 || !stableSessionId) {
      return;
    }
    setSending(true);
    try {
      const result = await sendAgentMessage(
        stableSessionId,
        getContent(),
        "marimo error report",
      );
      const outcomes = result.recipients.map(formatOutcome);
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

  return (
    <Button
      size="xs"
      variant="outline"
      disabled={sending || agents.length === 0 || !stableSessionId}
      onClick={send}
    >
      <SendIcon className="h-3 w-3 mr-2" />
      Send error to agent
    </Button>
  );
}
