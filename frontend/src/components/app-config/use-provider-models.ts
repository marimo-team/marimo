/* Copyright 2026 Marimo. All rights reserved. */
import { useState, useEffect } from "react";

export interface ProviderModelsResult {
  models: string[];
  isLoading: boolean;
  error: string | null;
}

/**
 * Fetches available models from an OpenAI-compatible endpoint
 * via the Marimo backend proxy to avoid CORS issues.
 */
export function useProviderModels(
  baseUrl: string | null | undefined,
): ProviderModelsResult {
  const [models, setModels] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!baseUrl) {
      setModels([]);
      setError(null);
      return;
    }

    const controller = new AbortController();

    const fetchModels = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams({ base_url: baseUrl });
        const response = await fetch(`/api/ai/models?${params}`, {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const data = (await response.json()) as { models: string[] };
        setModels(data.models ?? []);
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          return;
        }
        setError("Could not fetch models from endpoint");
        setModels([]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchModels();

    return () => controller.abort();
  }, [baseUrl]);

  return { models, isLoading, error };
}
