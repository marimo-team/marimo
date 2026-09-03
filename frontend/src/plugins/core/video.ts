/* Copyright 2026 Marimo. All rights reserved. */

interface VideoPlaybackConfig {
  src?: string | null;
  autoplay: boolean;
  muted: boolean;
  loop: boolean;
}

/** Create a compact React key for attributes that define video playback. */
export const createVideoPlaybackKey = (
  config: VideoPlaybackConfig,
  index?: number,
): string => {
  const sourceKey = config.src?.startsWith("data:")
    ? "data-url"
    : (config.src ?? "");
  return JSON.stringify([
    "video",
    sourceKey,
    config.autoplay,
    config.muted,
    config.loop,
    index,
  ]);
};
