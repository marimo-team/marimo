/* Copyright 2026 Marimo. All rights reserved. */

import { dequal } from "dequal";
import { atom, useAtomValue } from "jotai";
import { selectAtom } from "jotai/vanilla/utils";
import { useMemo } from "react";
import type { Attachment } from "@marimo-team/client/protocol";
import { activeNotebookReplicaAtom } from "../session/active-notebook";

export type { Attachment } from "@marimo-team/client/protocol";

const EMPTY_ATTACHMENTS: readonly Attachment[] = [];

/** Attachments visible to this session, empty while no notebook is available. */
export const notebookAttachmentsAtom = atom((get) => {
  const replica = get(activeNotebookReplicaAtom);
  return replica ? get(replica.attachmentsAtom) : EMPTY_ATTACHMENTS;
});

/** Current notebook attachments, optionally restricted to one kind. */
export function useNotebookAttachments(kind?: Attachment["kind"]) {
  const attachments = useMemo(
    () =>
      kind === undefined
        ? notebookAttachmentsAtom
        : selectAtom(
            notebookAttachmentsAtom,
            (value) => value.filter((attachment) => attachment.kind === kind),
            dequal,
          ),
    [kind],
  );
  return useAtomValue(attachments);
}

export function attachmentLabel(attachment: Attachment): string {
  return attachment.name || "Agent";
}
