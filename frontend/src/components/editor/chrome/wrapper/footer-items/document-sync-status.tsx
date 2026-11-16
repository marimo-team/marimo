/* Copyright 2026 Marimo. All rights reserved. */

import { atom, useAtomValue } from "jotai";
import { AlertCircleIcon } from "lucide-react";
import type React from "react";
import { activeDocumentModelAtom } from "@/core/session/active-notebook";
import { FooterItem } from "../footer-item";

/** The active notebook's document sync status, or null without a model. */
const syncStatusAtom = atom((get) => {
  const model = get(activeDocumentModelAtom);
  return model === null ? null : get(model.syncStatusAtom);
});

/**
 * Shown when this client's edits stop reaching the server.
 *
 * Typing keeps working locally and Run still uses the editor's code, but
 * other clients stop seeing the edits and Save fails until they are
 * through. A rejected edit is retried on click.
 */
export const DocumentSyncStatus: React.FC = () => {
  const model = useAtomValue(activeDocumentModelAtom);
  const status = useAtomValue(syncStatusAtom);
  if (model === null || status === null || status.status !== "error") {
    return null;
  }
  const retry = status.retryable
    ? () => {
        // The status shows the outcome, so a failed retry needs no handling.
        model.retry().catch(() => undefined);
      }
    : undefined;
  const detail = status.problem?.detail ?? status.error.message;
  return (
    <FooterItem
      tooltip={
        <div className="w-[260px] space-y-1">
          <div>Edits are not reaching the server.</div>
          <div className="text-muted-foreground">{detail}</div>
          <div>
            {retry ? "Click to retry." : "Reload the page to continue."}
          </div>
        </div>
      }
      selected={false}
      onClick={retry}
      aria-label="Edits are not reaching the server"
      data-testid="footer-document-sync"
    >
      <AlertCircleIcon className="w-4 h-4 text-destructive" />
    </FooterItem>
  );
};
