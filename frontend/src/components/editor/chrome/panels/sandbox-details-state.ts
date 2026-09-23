/* Copyright 2026 Marimo. All rights reserved. */
import { atom } from "jotai";
import { connectionNoticeAtom } from "@/core/network/connection-notice";
import { preparationAtom } from "@/core/packages/sandbox-state";

const preferenceAtom = atom<{
  preparationId: string | undefined;
  error: string | null;
  expanded: boolean;
} | null>(null);

const disclosureContextAtom = atom((get) => {
  const notice = get(connectionNoticeAtom);
  return {
    preparationId: get(preparationAtom)?.operation_id,
    error: notice && !notice.pending ? (notice.error ?? notice.title) : null,
  };
});

export const sandboxDetailsExpandedAtom = atom(
  (get) => {
    const context = get(disclosureContextAtom);
    const preference = get(preferenceAtom);
    if (
      preference &&
      preference.preparationId === context.preparationId &&
      preference.error === context.error
    ) {
      return preference.expanded;
    }
    // New work and failures open automatically. Completed startup stays quiet
    // unless the user chose to inspect it.
    return get(connectionNoticeAtom) !== null;
  },
  (get, set, expanded: boolean) => {
    set(preferenceAtom, { ...get(disclosureContextAtom), expanded });
  },
);
