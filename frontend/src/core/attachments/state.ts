/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import type { Attachment } from "@marimo-team/client/protocol";
import { notebookReplicaAtom } from "@/core/websocket/state";

export type { Attachment } from "@marimo-team/client/protocol";

export const agentAttachmentsAtom = atom((get) => {
  const notebook = get(notebookReplicaAtom);
  return (notebook ? get(notebook.attachmentsAtom) : []).filter(
    (attachment) => attachment.kind === "agent",
  );
});

export function attachmentLabel(attachment: Attachment): string {
  return attachment.name || "Agent";
}
