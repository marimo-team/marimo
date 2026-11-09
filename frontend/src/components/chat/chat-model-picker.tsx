/* Copyright 2026 Marimo. All rights reserved. */

import { useAtom, useAtomValue } from "jotai";
import {
  CheckIcon,
  ChevronDownIcon,
  GlobeIcon,
  SettingsIcon,
} from "lucide-react";
import { useId, useState } from "react";
import { AiProviderIcon } from "@/components/ai/ai-provider-icon";
import { getProviderLabel } from "@/components/ai/ai-model-dropdown";
import { getReasoningEffortOptions } from "@/components/ai/reasoning-options";
import { listModelsForAiSettings } from "@/components/ai/ai-utils";
import { useOpenSettingsToTab } from "@/components/app-config/state";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/utils/cn";
import { useAIConfigActions } from "@/core/ai/config";
import {
  AiModelId,
  type ProviderId,
  type QualifiedModelId,
} from "@/core/ai/ids/ids";
import { AiModelRegistry } from "@/core/ai/model-registry";
import { chatOptionsAtom } from "@/core/ai/state";
import { aiAtom } from "@/core/config/config";
import { DEFAULT_AI_MODEL } from "@/core/config/config-schema";

export function ChatModelPicker() {
  const [open, setOpen] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<ProviderId | null>(
    null,
  );
  const [search, setSearch] = useState("");
  const reasoningLabelId = useId();
  const webSearchId = useId();
  const ai = useAtomValue(aiAtom);
  const [options, setOptions] = useAtom(chatOptionsAtom);
  const { saveModelChange } = useAIConfigActions();
  const { handleClick } = useOpenSettingsToTab();
  const current = AiModelId.parse(ai?.models?.chat_model || DEFAULT_AI_MODEL);
  const registry = AiModelRegistry.create({
    customModels: [...(ai?.models?.custom_models ?? []), current.id],
    displayedModels: ai?.models?.displayed_models,
  });
  const currentModel = registry.getModel(current.id);
  const modelsByProvider = listModelsForAiSettings(
    registry.getListModelsByProvider(),
    ai,
  )
    .map(([provider, models]): [ProviderId, typeof models] => [
      provider,
      models.filter((model) => model.custom || model.roles.includes("chat")),
    ])
    .filter(([, models]) => models.length > 0);
  const activeProvider = selectedProvider ?? current.providerId;
  const providerModels = modelsByProvider.find(
    ([provider]) => provider === activeProvider,
  );
  const visibleProvider = providerModels?.[0] ?? modelsByProvider[0]?.[0];
  const visibleModels = providerModels?.[1] ?? modelsByProvider[0]?.[1] ?? [];
  const reasoningOptions = getReasoningEffortOptions(
    currentModel?.reasoning_options,
  );
  const supportsReasoning =
    reasoningOptions.length > 0 &&
    (current.providerId === "anthropic" ||
      current.providerId === "google" ||
      current.providerId === "bedrock" ||
      (current.providerId === "openai" &&
        (!ai?.open_ai?.base_url ||
          ai.open_ai.base_url.includes("api.openai.com"))));
  const effort = supportsReasoning ? options.reasoningEffort : null;
  const effortLabel = reasoningOptions.find(
    (option) => option.value === effort,
  )?.label;
  const displayName = currentModel?.name ?? current.shortModelId;

  return (
    <Popover
      open={open}
      onOpenChange={(open) => {
        setOpen(open);
        if (open) {
          setSelectedProvider(null);
          setSearch("");
        }
      }}
    >
      <PopoverTrigger asChild={true}>
        <Button
          variant="text"
          size="sm"
          aria-label={`Model: ${displayName}${effortLabel ? `, reasoning: ${effortLabel}` : ""}`}
          className="chat-control h-6 min-w-0 max-w-[200px] gap-1.5 px-2 text-xs font-normal"
        >
          <AiProviderIcon
            provider={current.providerId}
            className="size-3.5 shrink-0"
          />
          <span className="truncate">{displayName}</span>
          {effortLabel && (
            <span className="text-muted-foreground shrink-0">
              {effortLabel}
            </span>
          )}
          {options.webSearch && (
            <GlobeIcon
              className="size-3 shrink-0 text-muted-foreground"
              aria-label="Web search enabled"
            />
          )}
          <ChevronDownIcon className="size-3 shrink-0" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        side="top"
        align="end"
        className="chat-model-picker w-[420px] max-w-[calc(100vw-1rem)] p-0 overflow-hidden"
      >
        <div className="chat-model-picker-layout flex">
          <nav
            aria-label="Model providers"
            className="flex w-11 shrink-0 flex-col gap-1 overflow-y-auto border-r p-1 max-h-64"
          >
            {modelsByProvider.map(([provider]) => (
              <Button
                key={provider}
                variant="text"
                size="icon"
                aria-label={getProviderLabel(provider)}
                aria-pressed={provider === visibleProvider}
                title={getProviderLabel(provider)}
                className={cn(
                  "size-8 shrink-0 rounded-sm",
                  provider === visibleProvider &&
                    "bg-accent opacity-100 ring-1 ring-inset ring-border",
                )}
                onClick={() => {
                  setSelectedProvider(provider);
                  setSearch("");
                }}
              >
                <AiProviderIcon provider={provider} className="size-4" />
              </Button>
            ))}
          </nav>
          <Command className="min-w-0 flex-1 rounded-none">
            <CommandInput
              placeholder="Search models…"
              aria-label="Search models"
              value={search}
              onValueChange={setSearch}
              className="h-9 text-xs"
              rootClassName="px-2"
            />
            <CommandList
              className="h-55 max-h-55"
              aria-label={
                visibleProvider
                  ? `${getProviderLabel(visibleProvider)} models`
                  : "Models"
              }
            >
              <CommandEmpty>No models found.</CommandEmpty>
              <CommandGroup>
                {visibleModels.map((model) => {
                  const modelId: QualifiedModelId = `${model.provider}/${model.model}`;
                  return (
                    <CommandItem
                      key={modelId}
                      value={modelId}
                      aria-label={`${model.name} (${getProviderLabel(model.provider)})`}
                      keywords={[model.name]}
                      onSelect={() => {
                        saveModelChange(modelId, "chat");
                        if (modelId !== current.id) {
                          setOptions((previous) => ({
                            ...previous,
                            reasoningEffort: null,
                          }));
                        }
                      }}
                      className="gap-2 h-8 text-xs"
                    >
                      <span className="truncate">{model.name}</span>
                      {modelId === current.id && (
                        <CheckIcon className="ml-auto size-3.5 shrink-0" />
                      )}
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            </CommandList>
          </Command>
          <div className="chat-model-reasoning w-28 shrink-0 border-l p-1.5">
            <div
              id={reasoningLabelId}
              className="text-xs font-semibold text-muted-foreground h-6 px-1 flex items-center"
            >
              Reasoning
            </div>
            {supportsReasoning ? (
              <RadioGroup
                aria-labelledby={reasoningLabelId}
                className="gap-0"
                value={effort ?? "default"}
                onValueChange={(value) => {
                  const choice = reasoningOptions.find(
                    (option) => option.value === value,
                  );
                  if (choice) {
                    setOptions((previous) => ({
                      ...previous,
                      reasoningEffort:
                        choice.value === "default" ? null : choice.value,
                    }));
                  }
                }}
              >
                {reasoningOptions.map((option) => (
                  <label
                    key={option.value}
                    className="flex h-7 items-center justify-between gap-1.5 rounded px-1.5 text-xs cursor-pointer hover:bg-accent focus-within:ring-1 focus-within:ring-ring"
                  >
                    <RadioGroupItem value={option.value} className="sr-only" />
                    {option.label}
                    {(effort ?? "default") === option.value && (
                      <CheckIcon className="size-3.5" />
                    )}
                  </label>
                ))}
              </RadioGroup>
            ) : (
              <p className="text-xs text-muted-foreground leading-relaxed">
                This model uses its default reasoning settings.
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center justify-between gap-2 border-t px-2 py-1.5">
          <label
            htmlFor={webSearchId}
            className="flex items-center gap-2 text-xs cursor-pointer"
            title="Search the web when the model supports it."
          >
            <GlobeIcon className="size-3.5 text-muted-foreground" />
            Web search
            <Switch
              id={webSearchId}
              aria-label="Web search"
              size="xs"
              checked={options.webSearch}
              onCheckedChange={(webSearch) =>
                setOptions((previous) => ({ ...previous, webSearch }))
              }
            />
          </label>
          <Button
            variant="text"
            size="sm"
            className="h-6 gap-1.5 px-1 text-xs text-muted-foreground"
            onClick={() => {
              setOpen(false);
              handleClick("ai", "ai-models");
            }}
          >
            <SettingsIcon className="size-3.5" />
            Manage models
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
