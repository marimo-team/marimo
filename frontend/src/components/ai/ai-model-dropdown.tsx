/* Copyright 2024 Marimo. All rights reserved. */

import { capitalize } from "lodash-es";
import { ChevronDownIcon, CircleHelpIcon, Key } from "lucide-react";
import {
  AiModelId,
  isKnownAIProvider,
  type ProviderId,
  type QualifiedModelId,
} from "@/core/ai/ids/ids";
import { type AiModel, AiModelRegistry } from "@/core/ai/model-registry";
import { useResolvedMarimoConfig } from "@/core/config/config";
import { useAsyncData } from "@/hooks/useAsyncData";
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
import { Tooltip } from "../ui/tooltip";
import { AiProviderIcon } from "./ai-provider-icon";

type ModelTag = "chat" | "autocomplete" | "edit";

export const AIModelDropdown = ({
  value,
  placeholder,
  onSelect,
  triggerClassName,
  customDropdownContent,
  iconSize = "medium",
  showAddCustomModelDocs = false,
}: {
  value?: string;
  placeholder?: string;
  onSelect: (modelId: QualifiedModelId) => void;
  triggerClassName?: string;
  customDropdownContent?: React.ReactNode;
  iconSize?: "medium" | "small";
  showAddCustomModelDocs?: boolean;
}) => {
  const currentValue = value ? AiModelId.parse(value) : undefined;

  const selectModel = (modelId: QualifiedModelId) => {
    onSelect(modelId);
  };

  const [marimoConfig] = useResolvedMarimoConfig();
  const displayedModels = marimoConfig.ai?.models?.displayed_models;
  const customModels = marimoConfig.ai?.models?.custom_models;

  const { data: aiModelRegistry } = useAsyncData(async () => {
    return await AiModelRegistry.create(
      [
        "openrouter/deepseek-v1",
        "openrouter/gpt-4o",
        "anthropic/claude-3-5-sonnet",
      ],
      displayedModels,
    );
  }, [customModels, displayedModels]);
  const modelsByProvider = aiModelRegistry?.getGroupedModelsByProvider();

  // Only include autocompleteModel if copilot is set to "custom"
  const autocompleteModel =
    marimoConfig.completion.copilot === "custom"
      ? marimoConfig.ai?.models?.autocomplete_model
      : undefined;

  // Collect currently used models by their roles
  const modelTagMap = groupModelsIntoTags([
    { model: marimoConfig.ai?.models?.chat_model, tag: "chat" },
    { model: autocompleteModel, tag: "autocomplete" },
    { model: marimoConfig.ai?.models?.edit_model, tag: "edit" },
  ]);

  const iconSizeClass = iconSize === "medium" ? "h-4 w-4" : "h-3 w-3";

  const customModelIcon = (
    <Tooltip content="Custom model">
      <Key className="h-3 w-3" />
    </Tooltip>
  );

  const renderModelsUsedElsewhere = (model: string, tags: ModelTag[]) => {
    const modelId = AiModelId.parse(model);
    const isCustomModel = aiModelRegistry?.getCustomModels().has(modelId.id);

    return (
      <DropdownMenuItem onSelect={() => selectModel(modelId.id)}>
        <div className="flex items-center gap-2 w-full">
          <AiProviderIcon
            provider={modelId.providerId}
            className={iconSizeClass}
          />
          <span>{modelId.shortModelId}</span>
          {isCustomModel && customModelIcon}
          <div className="ml-auto flex gap-1">
            {tags.map((tag) => {
              const tagColour =
                tag === "chat"
                  ? "bg-purple-100 text-purple-800"
                  : tag === "autocomplete"
                    ? "bg-green-100 text-green-800"
                    : tag === "edit"
                      ? "bg-blue-100 text-blue-800"
                      : "bg-muted text-muted-foreground";
              return (
                <span
                  key={tag}
                  className={`text-xs px-1.5 py-0.5 rounded font-medium ${tagColour}`}
                >
                  {tag}
                </span>
              );
            })}
          </div>
        </div>
      </DropdownMenuItem>
    );
  };

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
        {Object.entries(modelTagMap).map(([modelId, tags]) =>
          renderModelsUsedElsewhere(modelId, tags),
        )}

        <DropdownMenuSeparator />

        {[...(modelsByProvider?.entries() ?? [])].map(([provider, models]) => (
          <ProviderDropdownContent
            key={provider}
            provider={provider}
            onSelect={selectModel}
            models={models}
            customModelIcon={customModelIcon}
            iconSizeClass={iconSizeClass}
          />
        ))}

        {customDropdownContent}

        {showAddCustomModelDocs && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="flex items-center gap-2">
              <a
                className="flex items-center gap-1"
                href="https://docs.marimo.io/guides/editor_features/ai_completion/?h=models#other-ai-providers"
                target="_blank"
                rel="noreferrer"
              >
                <CircleHelpIcon className="h-3 w-3" />
                <span>How to add a custom model</span>
              </a>
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export const ProviderDropdownContent = ({
  provider,
  onSelect,
  models,
  customModelIcon,
  iconSizeClass,
}: {
  provider: ProviderId;
  onSelect: (modelId: QualifiedModelId) => void;
  models: AiModel[];
  customModelIcon: React.ReactNode;
  iconSizeClass: string;
}) => {
  const iconProvider = isKnownAIProvider(provider)
    ? provider
    : "openai-compatible";

  if (models.length === 0) {
    return null;
  }

  return (
    <DropdownMenuSub>
      <DropdownMenuSubTrigger>
        <p className="flex items-center gap-2">
          <AiProviderIcon provider={iconProvider} className={iconSizeClass} />
          {getProviderLabel(provider)}
        </p>
      </DropdownMenuSubTrigger>
      <DropdownMenuPortal>
        <DropdownMenuSubContent>
          {models.map((model) => {
            const qualifiedModelId =
              `${provider}/${model.model}` as QualifiedModelId;
            return (
              <DropdownMenuItem
                key={qualifiedModelId}
                className="flex items-center gap-2"
                onSelect={() => {
                  onSelect(qualifiedModelId);
                }}
              >
                <AiProviderIcon
                  provider={iconProvider}
                  className={iconSizeClass}
                />
                <span>{model.model}</span>
                {model.custom && customModelIcon}
              </DropdownMenuItem>
            );
          })}
        </DropdownMenuSubContent>
      </DropdownMenuPortal>
    </DropdownMenuSub>
  );
};

function groupModelsIntoTags(
  models: Array<{ model?: string; tag: ModelTag }>,
): Record<QualifiedModelId, ModelTag[]> {
  const modelTagMap: Record<QualifiedModelId, ModelTag[]> = {};

  for (const model of models) {
    if (!model.model) {
      continue;
    }

    const modelId = AiModelId.parse(model.model);
    if (!modelTagMap[modelId.id]) {
      modelTagMap[modelId.id] = [];
    }
    modelTagMap[modelId.id].push(model.tag);
  }

  return modelTagMap;
}

function getProviderLabel(provider: ProviderId): string {
  switch (provider) {
    case "openai":
      return "OpenAI";
    case "anthropic":
      return "Anthropic";
    case "google":
      return "Google";
    case "deepseek":
      return "DeepSeek";
    case "bedrock":
      return "Bedrock";
    case "azure":
      return "Azure";
    case "ollama":
      return "Ollama";
    default:
      return capitalize(provider);
  }
}
