/* Copyright 2026 Marimo. All rights reserved. */

import { useAtom, useAtomValue } from "jotai";
import {
  CheckIcon,
  ChevronDownIcon,
  GlobeIcon,
  SettingsIcon,
} from "lucide-react";
import { useId, useMemo, useState } from "react";
import { AiProviderIcon } from "@/components/ai/ai-provider-icon";
import { getProviderLabel } from "@/components/ai/ai-model-dropdown";
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
import { useAsyncData } from "@/hooks/useAsyncData";
import { useRequestClient } from "@/core/network/requests";
import { toast } from "@/components/ui/use-toast";
import { getChatReasoningOptions } from "@/core/ai/reasoning-options";
import { cn } from "@/utils/cn";
import type { ReasoningEffortChoice } from "@/core/ai/reasoning-options";
import type { ChatOptions } from "@/core/network/types";
import { useAIConfigActions } from "@/core/ai/config";
import type { ProviderId, QualifiedModelId } from "@/core/ai/ids/ids";
import {
  getChatModelConfig,
  getEffectiveChatOptions,
} from "@/core/ai/chat-model-config";
import { chatOptionsAtom } from "@/core/ai/state";
import { aiAtom } from "@/core/config/config";

export function ChatModelPicker() {
  const [open, setOpen] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<ProviderId | null>(
    null,
  );
  const [search, setSearch] = useState("");
  const [isSavingModel, setIsSavingModel] = useState(false);
  const webSearchId = useId();
  const ai = useAtomValue(aiAtom);
  const [storedOptions, setOptions] = useAtom(chatOptionsAtom);
  const { getAiModelReasoning } = useRequestClient();
  const { saveModelChange } = useAIConfigActions();
  const { handleClick } = useOpenSettingsToTab();
  const { current, currentModel, registry, displayName } = useMemo(
    () => getChatModelConfig(ai),
    [ai],
  );
  const { data, isFetching } = useAsyncData(
    async () => ({
      model: current.id,
      config: ai,
      ...(await getAiModelReasoning({ model: current.id })),
    }),
    [ai, current.id, getAiModelReasoning],
  );
  const reasoningOptions = getChatReasoningOptions(
    currentModel,
    !isFetching && data?.model === current.id && data.config === ai
      ? data.efforts
      : [],
  );
  const options = getEffectiveChatOptions(storedOptions, reasoningOptions);

  const selectModel = async (modelId: QualifiedModelId) => {
    if (isSavingModel || modelId === current.id) {
      return;
    }
    setIsSavingModel(true);
    try {
      await saveModelChange(modelId, "chat");
      setOptions((previous) => ({ ...previous, reasoningEffort: null }));
    } catch {
      toast({
        title: "Couldn't change model",
        description: "Your previous model settings were kept.",
        variant: "danger",
      });
    }
    setIsSavingModel(false);
  };
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
  const effort = options.reasoningEffort;
  const effortLabel = reasoningOptions.find(
    (option) => option.value === effort,
  )?.label;
  const triggerLabel = [
    `Model: ${displayName}`,
    effortLabel && `reasoning: ${effortLabel}`,
    options.webSearch && "web search enabled",
  ]
    .filter(Boolean)
    .join(", ");

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
          aria-label={triggerLabel}
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
              aria-hidden={true}
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
                      disabled={isSavingModel}
                      onSelect={() => {
                        void selectModel(modelId);
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
          <ReasoningControls
            options={reasoningOptions}
            disabled={isSavingModel || isFetching}
            effort={effort}
            onChange={(reasoningEffort) =>
              setOptions((previous) => ({ ...previous, reasoningEffort }))
            }
          />
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

interface ReasoningControlsProps {
  options: ReasoningEffortChoice[];
  disabled: boolean;
  effort: ChatOptions["reasoningEffort"];
  onChange: (effort: ChatOptions["reasoningEffort"]) => void;
}

function ReasoningControls({
  options,
  disabled,
  effort,
  onChange,
}: ReasoningControlsProps) {
  const labelId = useId();
  return (
    <div className="chat-model-reasoning w-28 shrink-0 border-l p-1.5">
      <div
        id={labelId}
        className="text-xs font-semibold text-muted-foreground h-6 px-1 flex items-center"
      >
        Reasoning
      </div>
      {options.length > 0 ? (
        <RadioGroup
          disabled={disabled}
          aria-labelledby={labelId}
          className="gap-0"
          value={effort ?? "default"}
          onValueChange={(value) => {
            const choice = options.find((option) => option.value === value);
            if (choice) {
              onChange(choice.value === "default" ? null : choice.value);
            }
          }}
        >
          {options.map((option) => (
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
  );
}
