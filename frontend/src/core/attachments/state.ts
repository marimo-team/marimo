/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import type { Attachment } from "@/core/host/protocol";
import { notebookClientAtom } from "@/core/websocket/state";

export type { Attachment } from "@/core/host/protocol";

export const agentAttachmentsAtom = atom((get) => {
  const notebook = get(notebookClientAtom);
  return (notebook ? get(notebook.attachmentsAtom) : []).filter(
    (attachment) => attachment.kind === "agent",
  );
});

export function attachmentLabel(attachment: Attachment): string {
  return attachment.name || "Agent";
}
