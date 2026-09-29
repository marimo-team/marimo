/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import type { NotificationMessage } from "@/core/kernel/messages";

export type ParticipantPresence = Extract<
  NotificationMessage,
  { op: "participant-presence" }
>;

export const participantPresenceAtom = atom<ParticipantPresence | null>(null);
