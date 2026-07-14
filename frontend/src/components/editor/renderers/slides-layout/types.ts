/* Copyright 2026 Marimo. All rights reserved. */

import { z } from "zod";
import type { CellId } from "@/core/cells/ids";

const SlideTypeSchema = z.enum(["slide", "sub-slide", "fragment", "skip"]);
export type SlideType = z.infer<typeof SlideTypeSchema>;

const SlideConfigSchema = z.looseObject({
  type: SlideTypeSchema.optional(),
  speakerNotes: z.string().optional(),
  showCode: z.boolean().optional(),
});
export type SlideConfig = z.infer<typeof SlideConfigSchema>;

const DeckTransitionSchema = z.enum([
  "none",
  "fade",
  "slide",
  "convex",
  "concave",
  "zoom",
]);
export type DeckTransition = z.infer<typeof DeckTransitionSchema>;

const DeckContentAlignSchema = z.enum(["top", "center", "bottom"]);
export type DeckContentAlign = z.infer<typeof DeckContentAlignSchema>;

const DeckConfigSchema = z.looseObject({
  transition: DeckTransitionSchema.optional(),
  contentAlign: DeckContentAlignSchema.optional(),
});
export type DeckConfig = z.infer<typeof DeckConfigSchema>;

/**
 * Schema for the serialized form of a slides layout.
 *
 * This must be backwards-compatible as it is stored on the user's disk —
 * fields are optional so files saved before they existed (e.g. the bare `{}`
 * emitted by earlier marimo versions) still deserialize cleanly. Unknown
 * keys are preserved (via `looseObject`) for the same reason.
 */
export const SlidesLayoutSchema = z.looseObject({
  cells: z.array(SlideConfigSchema).optional(),
  deck: DeckConfigSchema.optional(),
});
export type SerializedSlidesLayout = z.infer<typeof SlidesLayoutSchema>;

/**
 * Runtime form of a slides layout.
 */
export interface SlidesLayout {
  cells: Map<CellId, SlideConfig>;
  deck: DeckConfig;
}
