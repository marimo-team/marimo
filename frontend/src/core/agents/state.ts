/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import {
  attachmentIdentity,
  attachmentLabel,
  notebookAttachmentsAtom,
} from "@/core/notebook";
import { uniqueByTakeLast } from "@/utils/arrays";

export const connectedAgentsAtom = atom((get) =>
  uniqueByTakeLast(
    get(notebookAttachmentsAtom).filter(
      (attachment) => attachment.kind === "agent",
    ),
    attachmentIdentity,
  ).map((attachment) => ({
    id: attachmentIdentity(attachment),
    name: attachmentLabel(attachment),
  })),
);
