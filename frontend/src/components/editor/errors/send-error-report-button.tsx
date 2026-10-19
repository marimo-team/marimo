/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { SendIcon } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  agentAttachmentsAtom,
  attachmentLabel,
} from "@/core/attachments/state";
import { agentToast } from "@/core/attachments/toast";
import { pairConfigAtom } from "@/core/config/pair";
import { stableSessionIdAtom } from "@/core/kernel/session";
import { API } from "@/core/network/api";
import { HTTPError, prettyError } from "@/utils/errors";

export function SendErrorReportButton({
  getContent,
}: {
  getContent: () => unknown;
}) {
  const hostEnabled = useAtomValue(pairConfigAtom)?.hostEnabled;
  const agents = useAtomValue(agentAttachmentsAtom);
  const stableSessionId = useAtomValue(stableSessionIdAtom);
  const [sending, setSending] = useState(false);

  if (!hostEnabled) {
    return null;
  }

  const send = async () => {
    if (sending || agents.length === 0 || !stableSessionId) {
      return;
    }
    setSending(true);
    try {
      await API.post<unknown, string>(
        `/pair/notebooks/${encodeURIComponent(stableSessionId)}/messages`,
        getContent(),
      );
      agentToast({
        title: `Sent to ${agents.map(attachmentLabel).join(", ")}`,
      });
    } catch (error) {
      agentToast({
        variant: "danger",
        title:
          error instanceof HTTPError && error.status === 409
            ? "No agent attached"
            : "Could not send error",
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
