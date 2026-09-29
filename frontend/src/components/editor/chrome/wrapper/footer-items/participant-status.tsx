/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { BotIcon } from "lucide-react";
import type React from "react";
import { useState } from "react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { pairPreviewAtom } from "@/core/config/pair";
import {
  type ParticipantPresence,
  participantPresenceAtom,
} from "@/core/participants/state";
import { useTimeAgo } from "@/hooks/useFormatting";
import { cn } from "@/utils/cn";
import { FooterItem } from "../footer-item";

const HARNESS_LABELS: Record<string, string> = {
  claude: "Claude Code",
  codex: "Codex",
  opencode: "OpenCode",
  unknown: "Agent",
};

export function getHarnessLabel(harness: string): string {
  return HARNESS_LABELS[harness.toLowerCase()] ?? "Agent";
}

export const ParticipantStatus: React.FC = () => {
  const pairPreview = useAtomValue(pairPreviewAtom);
  const presence = useAtomValue(participantPresenceAtom);

  if (!pairPreview || !presence) {
    return null;
  }

  return <ParticipantStatusItem presence={presence} />;
};

const ParticipantStatusItem: React.FC<{ presence: ParticipantPresence }> = ({
  presence,
}) => {
  const [open, setOpen] = useState(false);
  const timeAgo = useTimeAgo();
  const label = getHarnessLabel(presence.harness);
  const status = presence.attached ? "Connected" : "Disconnected";

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild={true}>
        <FooterItem
          tooltip={`${label}: ${status.toLowerCase()}`}
          selected={open}
          data-testid="footer-participant-status"
          aria-label={`${label}: ${status}`}
        >
          <span className="flex items-center gap-1.5">
            <span className="relative">
              <BotIcon className="w-4 h-4" />
              <span
                aria-hidden="true"
                className={cn(
                  "absolute -bottom-0.5 -right-0.5 size-1.5 rounded-full ring-1 ring-background",
                  presence.attached ? "bg-green-500" : "bg-muted-foreground",
                )}
              />
            </span>
            <span>{label}</span>
          </span>
        </FooterItem>
      </PopoverTrigger>
      <PopoverContent className="w-72">
        <div className="space-y-3 text-sm">
          <div>
            <h4 className="font-medium leading-none">{label}</h4>
            <p className="mt-1 text-muted-foreground">{status}</p>
          </div>
          <p>{label} connects through marimo pair.</p>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-muted-foreground">
            <dt>Last contact</dt>
            <dd>{timeAgo(presence.last_contact_at * 1000)}</dd>
            <dt>Participant</dt>
            <dd className="font-mono">{presence.participant_id.slice(0, 8)}</dd>
          </dl>
        </div>
      </PopoverContent>
    </Popover>
  );
};
