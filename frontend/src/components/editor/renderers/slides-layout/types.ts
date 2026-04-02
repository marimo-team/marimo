/* Copyright 2026 Marimo. All rights reserved. */
/* oxlint-disable typescript/no-empty-object-type */

/**
 * The serialized form of a slides layout.
 * This must be backwards-compatible as it is stored on the user's disk.
 */
// oxlint-disable-next-line typescript/consistent-type-definitions
export type SerializedSlidesLayout = {};

export interface SlidesLayout extends SerializedSlidesLayout {
  // No additional properties for now
}
