/* Copyright 2026 Marimo. All rights reserved. */

import { useEffect, useRef, useState } from "react";
import { z } from "zod";
import { API } from "@/core/network/api";
import { getRuntimeManager } from "@/core/runtime/config";
import { isWasm } from "@/core/wasm/utils";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { NativeSelect } from "../ui/native-select";

const CatalogSchema = z.object({
  models: z.array(z.object({ id: z.string().min(1), name: z.string() })),
});

const SAFE_ERRORS = new Set([
  "Model discovery requires the optional httpx dependency.",
  "Provider rejected the configured credentials or access.",
  "Provider model catalog request failed.",
  "Provider model discovery timed out.",
  "Unable to load the provider model catalog.",
  "Provider returned an invalid model catalog.",
  "Model discovery is not available.",
  "A saved provider base URL is required.",
  "Invalid provider base URL.",
  "OpenRouter API key not configured. Go to Settings > AI to configure.",
]);

interface ModelDiscoveryProps {
  provider: string;
  label: string;
  onSelect?: (modelId: string) => void;
  disabled?: boolean;
}

export function ModelDiscovery({
  provider,
  label,
  onSelect,
  disabled = false,
}: ModelDiscoveryProps) {
  const [models, setModels] = useState<z.infer<typeof CatalogSchema>["models"]>(
    [],
  );
  const [query, setQuery] = useState("");
  const [selection, setSelection] = useState("");
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const requestRef = useRef<AbortController | null>(null);

  useEffect(() => {
    requestRef.current?.abort();
    setModels([]);
    setQuery("");
    setSelection("");
    setLoaded(false);
    setLoading(false);
    setError("");
    return () => requestRef.current?.abort();
  }, [provider]);

  const search = query.trim().toLowerCase();
  const filtered = models.filter((model) =>
    `${model.name} ${model.id}`.toLowerCase().includes(search),
  );

  const load = async () => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    setLoading(true);
    setError("");
    try {
      const url = getRuntimeManager().httpURL;
      url.search = "";
      url.hash = "";
      url.pathname = `${url.pathname.replace(/\/$/, "")}/api/ai/models/${encodeURIComponent(provider)}`;
      const response = await fetch(url.toString(), {
        headers: API.headers(),
        signal: controller.signal,
      });
      if (!response.ok) {
        const raw = await response.text();
        let detail = raw.trim();
        try {
          const parsed = z
            .object({ detail: z.string() })
            .safeParse(JSON.parse(raw));
          detail = parsed.success ? parsed.data.detail : "";
        } catch {
          // Only allowlisted messages can be displayed, including plain text.
        }
        const fallback: Record<number, string> = {
          400: "Check the saved provider settings.",
          401: "Marimo authentication is required. Reload the editor.",
          403: "Access to model discovery was denied.",
          404: "Model discovery is not available for this provider or backend.",
          429: "Too many requests. Wait before retrying.",
          500: "Internal backend error. Check the server terminal.",
          501: "Live discovery is not supported for this provider yet. Use manual entry.",
          502: "The provider returned an error or invalid catalog.",
          503: "A required backend dependency or service is unavailable.",
          504: "The provider request timed out.",
        };
        if (!controller.signal.aborted) {
          setError(
            `HTTP ${response.status}: ${SAFE_ERRORS.has(detail) ? detail : (fallback[response.status] ?? "Model discovery failed.")}`,
          );
        }
        return;
      }
      const catalog = CatalogSchema.parse(await response.json());
      if (controller.signal.aborted) {
        return;
      }
      setModels(catalog.models);
      setSelection("");
      setLoaded(true);
    } catch {
      if (!controller.signal.aborted) {
        setError(
          "Unable to load a valid catalog. Check the connection and retry.",
        );
      }
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }
  };

  return (
    <div
      className="flex flex-col gap-2"
      data-testid={`model-discovery-${provider}`}
    >
      <Button
        type="button"
        variant="outline"
        size="xs"
        className="self-start"
        disabled={disabled || loading || isWasm()}
        onClick={load}
      >
        {loading ? "Loading models…" : "Load available models"}
      </Button>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      {loaded && (
        <>
          <output className="text-sm text-muted-secondary">
            {filtered.length} matching / {models.length} catalog models.
            {onSelect
              ? " Select a model to fill the Model field; click Add to save."
              : " Preview only; nothing is saved."}
          </output>
          <Input
            aria-label={`Search ${label} models`}
            placeholder="Search models…"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setSelection("");
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
              }
            }}
          />
          {filtered.length === 0 && <output>No models found</output>}
          <NativeSelect
            aria-label={`${label} catalog model`}
            value={selection}
            disabled={disabled || loading || filtered.length === 0}
            onChange={(event) => {
              const id = event.target.value;
              setSelection(id);
              setQuery(id);
              onSelect?.(id);
            }}
          >
            <option value="">Choose a model</option>
            {filtered.map((model) => (
              <option key={model.id} value={model.id}>
                {model.name} — {model.id}
              </option>
            ))}
          </NativeSelect>
        </>
      )}
    </div>
  );
}
