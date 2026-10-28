/* Copyright 2026 Marimo. All rights reserved. */

import { atom, useAtomValue } from "jotai";
import { useMemo } from "react";
import type { Attachment } from "@marimo-team/client/protocol";
import { notebookAttachmentsAtom } from "@/core/websocket/state";

export type { Attachment } from "@marimo-team/client/protocol";

/** Current notebook attachments, optionally restricted to one kind. */
export function useNotebookAttachments(kind?: Attachment["kind"]) {
  const attachments = useMemo(
    () =>
      kind === undefined
        ? notebookAttachmentsAtom
        : atom((get) =>
            get(notebookAttachmentsAtom).filter(
              (attachment) => attachment.kind === kind,
            ),
          ),
    [kind],
  );
  return useAtomValue(attachments);
}

export function attachmentLabel(attachment: Attachment): string {
  return attachment.name || "Agent";
}
