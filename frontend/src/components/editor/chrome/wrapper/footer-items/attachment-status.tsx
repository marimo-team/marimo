/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { BotIcon } from "lucide-react";
import { useState } from "react";
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
import { pairPreviewAtom } from "@/core/config/pair";
import { useTimeAgo } from "@/hooks/useFormatting";
import { Objects } from "@/utils/objects";
import { FooterItem } from "../footer-item";

export function AttachmentStatus() {
  const pairPreview = useAtomValue(pairPreviewAtom);
  const agents = useAtomValue(agentAttachmentsAtom);
  if (!pairPreview) {
    return null;
  }
  const groups = Objects.groupBy(
    agents,
    (attachment) =>
      attachment.identity
        ? `identity:${attachment.identity}`
        : `attachment:${attachment.id}`,
    (attachment) => attachment,
  );
  return Object.entries(groups).map(([identity, attachments]) => (
    <AttachmentStatusItem key={identity} attachments={attachments} />
  ));
}

function AttachmentStatusItem({ attachments }: { attachments: Attachment[] }) {
  const [open, setOpen] = useState(false);
  const timeAgo = useTimeAgo();
  const label = attachmentLabel(attachments[0]);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild={true}>
        <FooterItem
          asChild={true}
          tooltip={`${label}: connected`}
          selected={open}
          data-testid="footer-attachment-status"
          aria-label={`${label}: Connected`}
        >
          <button type="button">
            <span className="flex items-center gap-1.5">
              <BotIcon className="w-4 h-4" />
              <span className="max-w-48 truncate">{label}</span>
            </span>
          </button>
        </FooterItem>
      </PopoverTrigger>
      <PopoverContent className="w-64 text-sm">
        <h4 className="font-medium">{label}</h4>
        <ul className="space-y-2">
          {attachments.map((attachment) => (
            <li key={attachment.id}>
              <p
                className="truncate text-xs text-muted-foreground"
                title={attachment.id}
              >
                {attachment.id}
              </p>
              <p className="text-muted-foreground">
                Connected {timeAgo(attachment.since)}
              </p>
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
