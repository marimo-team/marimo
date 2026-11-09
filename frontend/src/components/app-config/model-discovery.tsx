/* Copyright 2026 Marimo. All rights reserved. */

import { useEffect, useRef, useState } from "react";
import { z } from "zod";
import { API } from "@/core/network/api";
import { getRuntimeManager } from "@/core/runtime/config";
import { isWasm } from "@/core/wasm/utils";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Popover as PopoverPrimitive } from "radix-ui";
import { Popover, PopoverContent } from "../ui/popover";

const CatalogSchema = z.object({
  models: z.array(z.object({ id: z.string().min(1), name: z.string() })),
});

interface ModelDiscoveryProps {
  provider: string;
  label: string;
  onSelect?: (modelId: string) => void;
  disabled?: boolean;
  value?: string;
  onValueChange?: (value: string) => void;
  inputId?: string;
  inputClassName?: string;
}

export function ModelDiscovery({
  provider,
  label,
  onSelect,
  disabled = false,
  value,
  onValueChange,
  inputId,
  inputClassName,
}: ModelDiscoveryProps) {
  const [models, setModels] = useState<z.infer<typeof CatalogSchema>["models"]>(
    [],
  );
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  const requestRef = useRef<AbortController | null>(null);

  useEffect(() => {
    requestRef.current?.abort();
    setModels([]);
    setQuery("");
    setOpen(false);
    setLoaded(false);
    setLoading(false);
    setError("");
    return () => requestRef.current?.abort();
  }, [provider]);

  const search = (value ?? query).trim().toLowerCase();
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
        let detail = "";

        try {
          const parsed = z
            .object({ detail: z.string() })
            .safeParse(JSON.parse(raw));

          detail = parsed.success ? parsed.data.detail : "";
        } catch {
          // The backend may return a non-JSON error response.
        }

        if (!controller.signal.aborted) {
          setError(
            detail ||
              "Unable to load the provider model catalog. Check the connection and retry.",
          );
        }

        return;
      }
      const catalog = CatalogSchema.parse(await response.json());
      if (controller.signal.aborted) {
        return;
      }
      setModels(catalog.models);
      setLoaded(true);
      setOpen(true);
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
      className="flex flex-col gap-2 sm:flex-row sm:items-end sm:gap-4"
      data-testid={`model-discovery-${provider}`}
    >
      <div className="relative min-w-0 flex-1">
        <Popover open={open && loaded} onOpenChange={setOpen}>
          <PopoverPrimitive.Anchor asChild>
            <div>
              <Input
                ref={inputRef}
                id={inputId}
                className={inputClassName ?? "w-full"}
                aria-label={label}
                aria-haspopup="dialog"
                aria-expanded={open && loaded}
                placeholder="Type a model ID or search…"
                value={value ?? query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  onValueChange?.(event.target.value);
                  setOpen(true);
                }}
                onFocus={() => setOpen(true)}
                onKeyDown={(event) => {
                  if (event.key === "Escape") {
                    setOpen(false);
                  }
                  if (event.key === "Enter") {
                    event.preventDefault();
                  }
                  if (event.key === "ArrowDown" && loaded) {
                    event.preventDefault();
                    setOpen(true);
                  }
                }}
              />
            </div>
          </PopoverPrimitive.Anchor>
          <PopoverContent
            align="start"
            className="w-[var(--radix-popover-trigger-width)] min-w-64 max-w-[calc(100vw-2rem)] p-1 text-sm"
            style={{
              maxHeight:
                "min(18rem, var(--radix-popover-content-available-height))",
              overflowY: "auto",
            }}
            onOpenAutoFocus={(event) => event.preventDefault()}
            onCloseAutoFocus={(event) => event.preventDefault()}
            onInteractOutside={(event) => {
              if (event.target === inputRef.current) {
                event.preventDefault();
              }
            }}
          >
            {filtered.length === 0 ? (
              <p className="px-2 py-1">No models found</p>
            ) : (
              filtered.map((model) => (
                <button
                  type="button"
                  key={model.id}
                  className="block w-full cursor-pointer rounded-sm px-2 py-1 text-left hover:bg-accent focus:bg-accent focus:outline-hidden"
                  onClick={() => {
                    setQuery(model.id);
                    onValueChange?.(model.id);
                    setOpen(false);
                    onSelect?.(model.id);
                    inputRef.current?.focus();
                    setOpen(false);
                  }}
                >
                  {model.name} — {model.id}
                </button>
              ))
            )}
          </PopoverContent>
        </Popover>
        {error && (
          <p role="alert" className="mt-1 text-sm text-destructive">
            {error}
          </p>
        )}
      </div>
      <Button
        type="button"
        variant="outline"
        size="xs"
        className="self-start sm:self-end"
        disabled={disabled || loading || isWasm()}
        onClick={load}
      >
        {loading ? "Loading models…" : "Search available models"}
      </Button>
    </div>
  );
}
