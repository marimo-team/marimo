/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import {
  BotIcon,
  CheckIcon,
  Loader2Icon,
  UnplugIcon,
  XIcon,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  type Attachment,
  agentAttachmentsAtom,
  attachmentLabel,
} from "@/core/attachments/state";
import { agentToast } from "@/core/attachments/toast";
import { pairConfigAtom } from "@/core/config/pair";
import { stableSessionIdAtom } from "@/core/kernel/session";
import { API } from "@/core/network/api";
import { useTimeAgo } from "@/hooks/useFormatting";
import { FooterItem } from "../footer-item";

export function AttachmentStatus() {
  const hostEnabled = useAtomValue(pairConfigAtom)?.hostEnabled;
  const agents = useAtomValue(agentAttachmentsAtom);
  const [open, setOpen] = useState(false);
  const previous = useRef(new Set<string>());
  const automatic = useRef(false);
  const pointerInside = useRef(false);
  const timeout = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const stopTimer = useCallback(() => clearTimeout(timeout.current), []);
  const startTimer = useCallback(() => {
    stopTimer();
    timeout.current = setTimeout(() => setOpen(false), 3000);
  }, [stopTimer]);
  const preserveEditorFocus = (event: Event) => {
    if (automatic.current) {
      event.preventDefault();
    }
  };

  useEffect(() => {
    if (!open) {
      pointerInside.current = false;
    }
    const current = new Set(
      hostEnabled ? agents.map((agent) => agent.identity ?? agent.id) : [],
    );
    const connected = [...current].some((id) => !previous.current.has(id));
    for (const id of current) {
      previous.current.add(id);
    }
    if (current.size === 0) {
      stopTimer();
      setOpen(false);
    } else if (connected) {
      if (open && !automatic.current) {
        return;
      }
      automatic.current = true;
      setOpen(true);
      if (!pointerInside.current) {
        startTimer();
      }
    }
  }, [agents, hostEnabled, open, startTimer, stopTimer]);

  useEffect(() => stopTimer, [stopTimer]);

  if (!hostEnabled || agents.length === 0) {
    return null;
  }
  const identities = new Set(agents.map((agent) => agent.identity ?? agent.id));
  const label =
    identities.size === 1
      ? `${attachmentLabel(agents[0])} connected`
      : `${identities.size} agents connected`;

  return (
    <Popover
      open={open}
      onOpenChange={(nextOpen) => {
        automatic.current = false;
        stopTimer();
        setOpen(nextOpen);
      }}
    >
      <PopoverTrigger asChild={true}>
        <FooterItem
          asChild={true}
          tooltip={label}
          selected={open}
          data-testid="footer-attachment-status"
          aria-label={label}
        >
          <button type="button">
            <span className="flex items-center gap-1.5">
              <BotIcon className="w-4 h-4" />
              <span className="max-w-48 truncate">{label}</span>
            </span>
          </button>
        </FooterItem>
      </PopoverTrigger>
      <PopoverContent
        className="w-80 p-0 text-sm"
        side="top"
        align="start"
        onOpenAutoFocus={preserveEditorFocus}
        onCloseAutoFocus={preserveEditorFocus}
        onPointerEnter={() => {
          pointerInside.current = true;
          stopTimer();
        }}
        onPointerLeave={() => {
          pointerInside.current = false;
          if (automatic.current) {
            startTimer();
          }
        }}
        onFocusCapture={() => {
          automatic.current = false;
          stopTimer();
        }}
      >
        <h4 className="font-medium px-4 py-3 border-b">{label}</h4>
        <div className="max-h-72 overflow-auto divide-y">
          {agents.map((attachment) => (
            <AttachmentStatusItem key={attachment.id} attachment={attachment} />
          ))}
        </div>
        <p className="px-4 py-3 border-t text-xs text-muted-foreground">
          Disconnect removes the notebook connection. The agent session keeps
          running.
        </p>
      </PopoverContent>
    </Popover>
  );
}

function AttachmentStatusItem({ attachment }: { attachment: Attachment }) {
  const stableSessionId = useAtomValue(stableSessionIdAtom);
  const [state, setState] = useState<"idle" | "confirming" | "disconnecting">(
    "idle",
  );
  const confirming = state !== "idle";
  const disconnecting = state === "disconnecting";
  const disconnectButton = useRef<HTMLButtonElement>(null);
  const timeAgo = useTimeAgo();
  const label = attachmentLabel(attachment);
  const disconnectLabel = disconnecting
    ? `Disconnecting ${label}`
    : confirming
      ? `Confirm disconnect ${label}`
      : `Disconnect ${label}`;

  const disconnect = async () => {
    if (disconnecting || !stableSessionId) {
      return;
    }
    setState("disconnecting");
    try {
      await API.post(
        `/pair/notebooks/${encodeURIComponent(stableSessionId)}/attachments/detach`,
        { attachment_id: attachment.id },
      );
    } catch {
      agentToast({ variant: "danger", title: `Could not disconnect ${label}` });
    } finally {
      setState("idle");
    }
  };

  return (
    <div className="flex items-start gap-3 px-4 py-3">
      <div className="min-w-0 flex-1">
        <h5 className="font-medium">{label}</h5>
        <p className="text-xs text-muted-foreground mt-1">
          Connected {timeAgo(attachment.since)}
        </p>
        <p
          className="text-xs font-mono text-muted-foreground truncate mt-1"
          title={attachment.id}
        >
          {attachment.id}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        {confirming && (
          <span className="text-xs text-muted-foreground">
            {disconnecting ? "Disconnecting…" : "Disconnect?"}
          </span>
        )}
        <Button
          ref={disconnectButton}
          size="icon"
          variant="outlineDestructive"
          disabled={disconnecting || !stableSessionId}
          onClick={confirming ? disconnect : () => setState("confirming")}
          aria-label={disconnectLabel}
          title={disconnectLabel}
          aria-busy={disconnecting}
        >
          {disconnecting ? (
            <Loader2Icon className="size-3.5 animate-spin" aria-hidden={true} />
          ) : confirming ? (
            <CheckIcon className="size-3.5" aria-hidden={true} />
          ) : (
            <UnplugIcon className="size-3.5" aria-hidden={true} />
          )}
        </Button>
        {confirming && (
          <Button
            size="icon"
            variant="outline"
            disabled={disconnecting}
            onClick={() => {
              setState("idle");
              disconnectButton.current?.focus();
            }}
            aria-label={`Cancel disconnect ${label}`}
            title={`Cancel disconnect ${label}`}
          >
            <XIcon className="size-3.5" aria-hidden={true} />
          </Button>
        )}
      </div>
    </div>
  );
}
