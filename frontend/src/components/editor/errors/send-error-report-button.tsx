/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { SendIcon } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/use-toast";
import {
  agentAttachmentsAtom,
  attachmentLabel,
} from "@/core/attachments/state";
import { pairPreviewAtom } from "@/core/config/pair";
import { stableSessionIdAtom } from "@/core/kernel/session";
import { API } from "@/core/network/api";
import { HTTPError } from "@/utils/errors";

export function SendErrorReportButton({
  getContent,
}: {
  getContent: () => unknown;
}) {
  const pairPreview = useAtomValue(pairPreviewAtom);
  const agents = useAtomValue(agentAttachmentsAtom);
  const stableSessionId = useAtomValue(stableSessionIdAtom);
  const [sending, setSending] = useState(false);

  if (!pairPreview) {
    return null;
  }

  const send = async () => {
    if (sending || agents.length === 0 || !stableSessionId) {
      return;
    }
    setSending(true);
    try {
      await API.post<unknown, string>(
        `/pair/notebooks/${encodeURIComponent(stableSessionId)}/handoffs`,
        getContent(),
      );
      toast({ title: `Sent to ${agents.map(attachmentLabel).join(", ")}` });
    } catch (error) {
      toast({
        variant: "danger",
        title:
          error instanceof HTTPError && error.status === 409
            ? "No agent attached"
            : "Could not send error",
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
