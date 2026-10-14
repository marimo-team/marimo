/* Copyright 2026 Marimo. All rights reserved. */

import type { components } from "@marimo-team/marimo-api";
import { atom } from "jotai";
import { isConnectedAtom } from "@/core/network/connection";

export type Attachment = components["schemas"]["Attachment"];

export const attachmentsAtom = atom<Attachment[]>([]);
export const agentAttachmentsAtom = atom((get) => {
  if (!get(isConnectedAtom)) {
    return [];
  }
  return get(attachmentsAtom).filter(
    (attachment) => attachment.kind === "agent",
  );
});

export function attachmentLabel(attachment: Attachment): string {
  return attachment.name || "Agent";
}
