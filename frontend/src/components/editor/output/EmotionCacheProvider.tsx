/* Copyright 2024 Marimo. All rights reserved. */

import createCache from "@emotion/cache";
import { CacheProvider } from "@emotion/react";
import { type PropsWithChildren, useMemo } from "react";

/**
 * Custom Emotion cache provider that works in shadow roots.
 * We don't directly use Emotion, but some of our dependencies do (via MUI).
 */
export const EmotionCacheProvider: React.FC<
  PropsWithChildren<{ container: ShadowRoot | null }>
> = ({ container, children }) => {
  const cache = useMemo(() => {
    if (!container) {
      return createCache({ key: "mo", prepend: true });
    }
    let emotionRoot = container.querySelector("style");
    // Create a new style element if one doesn't exist
    if (!emotionRoot) {
      emotionRoot = document.createElement("style");
      container.append(emotionRoot);
    }
    return createCache({
      key: "mo",
      prepend: true,
      container: emotionRoot,
    });
  }, [container]);

  return <CacheProvider value={cache}>{children}</CacheProvider>;
};
