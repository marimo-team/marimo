/* Copyright 2024 Marimo. All rights reserved. */

/**
 * The serialized form of a slides layout.
 * This must be backwards-compatible as it is stored on the user's disk.
 */
export type SerializedSlidesLayout = {};

export interface SlidesLayout extends SerializedSlidesLayout {
  // No additional properties for now
}
