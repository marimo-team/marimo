/* Copyright 2026 Marimo. All rights reserved. */

import { Popover as PopoverPrimitive } from "radix-ui";
import { useRef, useState } from "react";
import { listProviderModels } from "@/core/network/ai";
import { isWasm } from "@/core/wasm/utils";
import { useAsyncData } from "@/hooks/useAsyncData";
import { useDeepCompareMemoize } from "@/hooks/useDeepCompareMemoize";
import { prettyError } from "@/utils/errors";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Popover, PopoverContent } from "../ui/popover";
import type { ModelProviderConfig } from "./model-provider-config";

interface ModelDiscoveryProps {
  provider: string;
  configuration: ModelProviderConfig;
  label: string;
  disabled: boolean;
  value: string;
  onValueChange: (value: string) => void;
  inputId: string;
  inputClassName?: string;
}

export function ModelDiscovery({
  provider,
  configuration,
  label,
  disabled,
  value,
  onValueChange,
  inputId,
  inputClassName,
}: ModelDiscoveryProps) {
  const query = useDeepCompareMemoize({ provider, configuration });
  const [requestedQuery, setRequestedQuery] = useState<typeof query | null>(
    null,
  );
  const requested = requestedQuery === query;
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const optionsRef = useRef<HTMLDivElement>(null);
  const focusOptionsOnOpen = useRef(false);
  const { data, error, isFetching, refetch } = useAsyncData(async () => {
    if (!requested || disabled) {
      return;
    }
    const catalog = await listProviderModels(provider);
    return { query, ...catalog };
  }, [query, requested, disabled]);

  const catalog = requested && data?.query === query ? data : undefined;
  const catalogError = requested ? error : undefined;
  const loading = requested && !disabled && isFetching;
  const search = value.trim().toLowerCase();
  const filtered = catalog?.models.filter((model) =>
    `${model.name} ${model.id}`.toLowerCase().includes(search),
  );

  return (
    <div className="flex min-w-0 flex-col gap-2">
      <Popover open={open && !!catalog && !disabled} onOpenChange={setOpen}>
        <PopoverPrimitive.Anchor asChild={true}>
          <div>
            <Input
              ref={inputRef}
              id={inputId}
              className={inputClassName}
              aria-label={label}
              aria-haspopup="dialog"
              aria-expanded={open && !!catalog && !disabled}
              placeholder="Type a model ID or search…"
              value={value}
              onChange={(event) => {
                onValueChange(event.target.value);
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
                if (event.key === "ArrowDown" && catalog) {
                  event.preventDefault();
                  focusOptionsOnOpen.current = !open;
                  setOpen(true);
                  optionsRef.current?.querySelector("button")?.focus();
                }
              }}
            />
          </div>
        </PopoverPrimitive.Anchor>
        <PopoverContent
          ref={optionsRef}
          align="start"
          className="w-[var(--radix-popover-trigger-width)] min-w-64 max-w-[calc(100vw-2rem)] max-h-72 overflow-y-auto p-1 text-sm"
          onOpenAutoFocus={(event) => {
            if (!focusOptionsOnOpen.current) {
              event.preventDefault();
            }
            focusOptionsOnOpen.current = false;
          }}
          onCloseAutoFocus={(event) => event.preventDefault()}
          onInteractOutside={(event) => {
            if (event.target === inputRef.current) {
              event.preventDefault();
            }
          }}
        >
          {filtered?.length === 0 && (
            <p className="px-2 py-1">No models found</p>
          )}
          {filtered?.map((model) => (
            <button
              type="button"
              key={model.id}
              className="block w-full cursor-pointer rounded-sm px-2 py-1 text-left hover:bg-accent focus:bg-accent focus:outline-hidden"
              onClick={() => {
                onValueChange(model.id);
                inputRef.current?.focus();
                setOpen(false);
              }}
            >
              {model.name} — {model.id}
            </button>
          ))}
        </PopoverContent>
      </Popover>
      {catalogError && (
        <p role="alert" className="text-sm text-destructive">
          {prettyError(catalogError)}
        </p>
      )}
      <Button
        type="button"
        variant="outline"
        size="xs"
        className="self-start"
        disabled={disabled || loading || isWasm()}
        onClick={() => {
          setOpen(true);
          if (requested) {
            refetch();
          } else {
            setRequestedQuery(query);
          }
        }}
      >
        {loading ? "Loading models…" : "Search available models"}
      </Button>
    </div>
  );
}
