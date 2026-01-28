/* Copyright 2026 Marimo. All rights reserved. */
import type { ReactNode } from "react";
import {
  useEmbeddingFeature,
  type EmbeddingFeaturesConfig,
} from "./embedding";

interface Props {
  feature: keyof EmbeddingFeaturesConfig;
  children: ReactNode;
}

/**
 * Conditionally renders children based on embedding feature configuration.
 *
 * When embedding mode is disabled, children are always rendered.
 * When embedding mode is enabled, children are only rendered if the
 * specified feature is explicitly enabled in the embedding config.
 */
export const IfEmbeddingFeature: React.FC<Props> = ({ feature, children }) => {
  const enabled = useEmbeddingFeature(feature);
  return enabled ? children : null;
};
