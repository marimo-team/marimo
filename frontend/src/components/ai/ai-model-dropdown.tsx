/* Copyright 2024 Marimo. All rights reserved. */

import { ChevronDownIcon, CircleHelpIcon } from "lucide-react";
import { useResolvedMarimoConfig } from "@/core/config/config";
import {
  AiModelId,
  isKnownAIProvider,
  type ProviderId,
  type QualifiedModelId,
} from "@/utils/ai/ids";
import { getAIModelsByProvider } from "../app-config/constants";
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
  const modelsByProvider = getAIModelsByProvider(displayedModels);
  const customModels = marimoConfig.ai?.models?.custom_models;
  const customModelIds = customModels?.map((model) => AiModelId.parse(model));

  // Only include autocompleteModel if copilot is set to "custom"
  const autocompleteModel =
    marimoConfig.completion.copilot === "custom"
      ? marimoConfig.ai?.models?.autocomplete_model
      : undefined;

  // Collect all models and their tags
  const modelTagMap = groupModelsIntoTags([
    { model: marimoConfig.ai?.models?.chat_model, tag: "chat" },
    { model: autocompleteModel, tag: "autocomplete" },
    { model: marimoConfig.ai?.models?.edit_model, tag: "edit" },
  ]);

  const iconSizeClass = iconSize === "medium" ? "h-4 w-4" : "h-3 w-3";

  const renderModelsUsedElsewhere = (model: string, tags: ModelTag[]) => {
    const modelId = AiModelId.parse(model);

    return (
      <DropdownMenuItem onSelect={() => selectModel(modelId.id)}>
        <p className="flex items-center gap-2 w-full">
          <AiProviderIcon provider={modelId.providerId} className="h-3 w-3" />
          <span>{modelId.shortModelId}</span>
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
        </p>
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

        {/* Custom models at the top since they are specified by the user */}
        <ProviderDropdownContent
          provider="custom-models"
          providerLabel="Custom models"
          onSelect={selectModel}
          models={customModelIds ?? []}
        />

        <ProviderDropdownContent
          provider="openai"
          providerLabel="OpenAI"
          onSelect={selectModel}
          models={modelsByProvider.openai}
        />

        <ProviderDropdownContent
          provider="anthropic"
          providerLabel="Anthropic"
          onSelect={selectModel}
          models={modelsByProvider.anthropic}
        />

        <ProviderDropdownContent
          provider="google"
          providerLabel="Google"
          onSelect={selectModel}
          models={modelsByProvider.google}
        />

        <ProviderDropdownContent
          provider="deepseek"
          providerLabel="DeepSeek"
          onSelect={selectModel}
          models={modelsByProvider.deepseek}
        />

        <ProviderDropdownContent
          provider="bedrock"
          providerLabel="Bedrock"
          onSelect={selectModel}
          models={modelsByProvider.bedrock}
        />

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
  providerLabel,
  onSelect,
  models,
}: {
  provider: ProviderId | "custom-models";
  providerLabel: string;
  onSelect: (modelId: QualifiedModelId) => void;
  models: AiModelId[];
}) => {
  const iconProvider =
    provider === "custom-models" ? "openai-compatible" : provider;

  if (models.length === 0) {
    return null;
  }

  return (
    <DropdownMenuSub>
      <DropdownMenuSubTrigger>
        <p className="flex items-center gap-2">
          <AiProviderIcon provider={iconProvider} className="h-3 w-3" />
          {providerLabel}
        </p>
      </DropdownMenuSubTrigger>
      <DropdownMenuPortal>
        <DropdownMenuSubContent>
          {models.map((model) => (
            <DropdownMenuItem
              key={model.id}
              className="flex items-center gap-2"
              onSelect={() => onSelect(model.id)}
            >
              <AiProviderIcon provider={iconProvider} className="h-3 w-3" />
              <span>{model.shortModelId}</span>
            </DropdownMenuItem>
          ))}
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
