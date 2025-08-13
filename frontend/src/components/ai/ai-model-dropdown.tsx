/* Copyright 2024 Marimo. All rights reserved. */

import { ChevronDownIcon } from "lucide-react";
import { AiModelId, isKnownAIProvider, type ProviderId } from "@/utils/ai/ids";
import { KNOWN_AI_MODEL_IDS, KNOWN_AI_MODELS } from "../app-config/constants";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuPortal,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { AiProviderIcon } from "./ai-provider-icon";

export const AIModelDropdown = ({
  value,
  placeholder,
  onSelect,
  triggerClassName,
  customDropdownContent,
  iconSize = "medium",
}: {
  value?: string;
  placeholder?: string;
  onSelect: (modelId: string) => void;
  triggerClassName?: string;
  customDropdownContent?: React.ReactNode;
  iconSize?: "medium" | "small";
}) => {
  const currentValue = value ? AiModelId.parse(value) : undefined;

  const selectModel = (modelId: string) => {
    onSelect(modelId);
  };

  const iconSizeClass = iconSize === "medium" ? "h-4 w-4" : "h-3 w-3";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={`flex items-center justify-between px-2 py-0.5 border rounded-md 
            hover:bg-accent hover:text-accent-foreground ${triggerClassName}`}
      >
        <div className="flex items-center gap-2">
          {currentValue ? (
            <>
              <AiProviderIcon
                provider={currentValue.providerId}
                className={iconSizeClass}
              />
              <span className="truncate">
                {isKnownAIProvider(currentValue.providerId)
                  ? currentValue.shortModelId
                  : currentValue.id}
              </span>
            </>
          ) : (
            <span className="text-muted-foreground truncate">
              {placeholder}
            </span>
          )}
        </div>
        <ChevronDownIcon className={`${iconSizeClass} ml-1`} />
      </DropdownMenuTrigger>

      <DropdownMenuContent>
        {/* Display current model if it's not included in the known models list */}
        {currentValue &&
          !(KNOWN_AI_MODELS as readonly string[]).includes(currentValue.id) && (
            <>
              <DropdownMenuItem
                onSelect={() => selectModel(currentValue.id)}
                className="flex items-center gap-2"
              >
                <AiProviderIcon
                  provider={currentValue.providerId}
                  className="h-3 w-3"
                />
                <span>{currentValue.shortModelId}</span>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
            </>
          )}

        <ProviderDropdownContent
          provider="openai"
          providerLabel="OpenAI"
          onSelect={selectModel}
        />

        <ProviderDropdownContent
          provider="anthropic"
          providerLabel="Anthropic"
          onSelect={selectModel}
        />

        <ProviderDropdownContent
          provider="google"
          providerLabel="Google"
          onSelect={selectModel}
        />

        <ProviderDropdownContent
          provider="deepseek"
          providerLabel="DeepSeek"
          onSelect={selectModel}
        />

        <ProviderDropdownContent
          provider="bedrock"
          providerLabel="Bedrock"
          onSelect={selectModel}
        />

        {customDropdownContent}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export const ProviderDropdownContent = ({
  provider,
  providerLabel,
  onSelect,
}: {
  provider: ProviderId;
  providerLabel: string;
  onSelect: (modelId: string) => void;
}) => {
  return (
    <DropdownMenuSub>
      <DropdownMenuSubTrigger>
        <p className="flex items-center gap-2">
          <AiProviderIcon provider={provider} className="h-3 w-3" />
          {providerLabel}
        </p>
      </DropdownMenuSubTrigger>
      <DropdownMenuPortal>
        <DropdownMenuSubContent>
          {KNOWN_AI_MODEL_IDS.filter(
            (model) => model.providerId === provider,
          ).map((model) => (
            <DropdownMenuItem
              key={model.id}
              className="flex items-center gap-2"
              onSelect={() => onSelect(model.id)}
            >
              <AiProviderIcon provider={provider} className="h-3 w-3" />
              <span>{model.shortModelId}</span>
            </DropdownMenuItem>
          ))}
        </DropdownMenuSubContent>
      </DropdownMenuPortal>
    </DropdownMenuSub>
  );
};
