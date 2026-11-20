/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import { z } from "zod";

export const pairConfigSchema = z.object({
  command: z.string(),
  hostEnabled: z.boolean().default(false),
  templates: z.object({
    prompt: z.string(),
    notebook: z.string(),
    session: z.string(),
    token_file: z.string(),
    token: z.string(),
  }),
});

export type PairConfig = z.infer<typeof pairConfigSchema>;

export const pairConfigAtom = atom<PairConfig | undefined>(undefined);
