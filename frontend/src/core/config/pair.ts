/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import { z } from "zod";

export const pairPreviewSchema = z.object({
  command: z.string(),
  templates: z.object({
    prompt: z.string(),
    file: z.string(),
    session: z.string(),
    token_file: z.string(),
    token: z.string(),
  }),
});

export type PairPreviewConfig = z.infer<typeof pairPreviewSchema>;

export const pairPreviewAtom = atom<PairPreviewConfig | undefined>(undefined);
