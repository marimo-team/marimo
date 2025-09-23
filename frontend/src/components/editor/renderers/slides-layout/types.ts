/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-empty-interface */

/**
 * The serialized form of a slides layout.
 * This must be backwards-compatible as it is stored on the user's disk.
 */
// eslint-disable-next-line @typescript-eslint/no-empty-object-type
export interface SerializedSlidesLayout {}

export interface SlidesLayout extends SerializedSlidesLayout {
  // No additional properties for now
}
