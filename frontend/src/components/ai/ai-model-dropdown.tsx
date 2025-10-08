/* Copyright 2024 Marimo. All rights reserved. */

import type { Role } from "@marimo-team/llm-info";
import { useAtomValue } from "jotai";
import { capitalize } from "lodash-es";
import {
  BotIcon,
  BrainIcon,
  ChevronDownIcon,
  CircleHelpIcon,
} from "lucide-react";
import React from "react";
import { type SupportedRole, useModelChange } from "@/core/ai/config";
import {
  AiModelId,
  isKnownAIProvider,
  type ProviderId,
  type QualifiedModelId,
} from "@/core/ai/ids/ids";
import { type AiModel, AiModelRegistry } from "@/core/ai/model-registry";
import { aiAtom, completionAtom } from "@/core/config/config";
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
import { getCurrentRoleTooltip, getTagColour } from "./display-helpers";

interface AIModelDropdownProps {
  value?: string;
  placeholder?: string;
  onSelect?: (modelId: QualifiedModelId) => void;
  triggerClassName?: string;
  customDropdownContent?: React.ReactNode;
  iconSize?: "medium" | "small";
  showAddCustomModelDocs?: boolean;
  displayIconOnly?: boolean;
  forRole: SupportedRole;
}

export const AIModelDropdown = ({
  value,
  placeholder,
  onSelect,
  triggerClassName,
  customDropdownContent,
  iconSize = "medium",
  showAddCustomModelDocs = false,
  forRole,
  displayIconOnly = false,
}: AIModelDropdownProps) => {
  const [isOpen, setIsOpen] = React.useState(false);

  const ai = useAtomValue(aiAtom);
  const completion = useAtomValue(completionAtom);
  const { saveModelChange } = useModelChange();

  // Only include autocompleteModel if copilot is set to "custom"
  const autocompleteModel =
    completion.copilot === "custom"
      ? ai?.models?.autocomplete_model
      : undefined;

  const aiModelRegistry = AiModelRegistry.create({
    // We add all the custom models and the models used in the editor.
    // If they among the known models, they won't overwrite them.
    customModels: [
      ...(ai?.models?.custom_models ?? []),
      ai?.models?.chat_model,
      autocompleteModel,
      ai?.models?.edit_model,
    ].filter(Boolean),
    displayedModels: ai?.models?.displayed_models,
    inferenceProfiles: ai?.models?.inference_profiles || {},
  });
  const modelsByProvider = aiModelRegistry.getListModelsByProvider();

  const activeModel =
    forRole === "autocomplete"
      ? ai?.models?.autocomplete_model
      : forRole === "chat"
        ? ai?.models?.chat_model
        : forRole === "edit"
          ? ai?.models?.edit_model
          : undefined;

  // If value is provided, use it, otherwise use the active model
  const currentValue = value
    ? AiModelId.parse(value)
    : activeModel
      ? AiModelId.parse(activeModel)
      : undefined;

  const iconSizeClass = iconSize === "medium" ? "h-4 w-4" : "h-3 w-3";

  // Get the current inference profile for models that support them
  const inferenceProfiles = ai?.models?.inference_profiles || {};
  const currentModel = currentValue
    ? aiModelRegistry.getModel(currentValue.id)
    : undefined;
  const hasInferenceProfiles =
    currentModel?.inference_profiles &&
    currentModel.inference_profiles.length > 0;
  const currentProfile = hasInferenceProfiles
    ? (inferenceProfiles[currentValue!.shortModelId] as string | undefined) ||
      "none"
    : undefined;

  // Compute display text with inference profile for models that support them
  const displayText = currentValue
    ? hasInferenceProfiles && currentProfile && currentProfile !== "none"
      ? `${currentProfile}.${currentValue.shortModelId}`
      : isKnownAIProvider(currentValue.providerId)
        ? currentValue.shortModelId
        : currentValue.id
    : undefined;

  const renderModelWithRole = (modelId: AiModelId, role: Role) => {
    const maybeModelMatch = aiModelRegistry.getModel(modelId.id);

    // Get inference profile for models that support them
    // TODO this smells
    const modelHasInferenceProfiles =
      maybeModelMatch?.inference_profiles &&
      maybeModelMatch.inference_profiles.length > 0;
    const modelProfile = modelHasInferenceProfiles
      ? (inferenceProfiles[modelId.shortModelId] as string | undefined) ||
        "none"
      : undefined;

    // Compute display ID with inference profile
    const displayId =
      modelHasInferenceProfiles && modelProfile && modelProfile !== "none"
        ? `${modelId.providerId}/${modelProfile}.${modelId.shortModelId}`
        : modelId.id;

    return (
      <div className="flex items-center gap-2 w-full px-2 py-1">
        <AiProviderIcon
          provider={modelId.providerId}
          className={iconSizeClass}
        />
        <div className="flex flex-col">
          <span>{maybeModelMatch?.name || modelId.shortModelId}</span>
          <span className="text-xs text-muted-foreground">{displayId}</span>
        </div>

        <div className="ml-auto flex gap-1">
          <Tooltip content={getCurrentRoleTooltip(role)}>
            <span
              key={role}
              className={`text-xs px-1.5 py-0.5 rounded font-medium ${getTagColour(role)}`}
            >
              {role}
            </span>
          </Tooltip>
        </div>
      </div>
    );
  };

  const handleSelect = (modelId: QualifiedModelId) => {
    if (onSelect) {
      onSelect(modelId);
    } else {
      saveModelChange(modelId, forRole);
    }
    setIsOpen(false);
  };

  return (
    <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuTrigger
        className={`flex items-center justify-between px-2 py-0.5 border rounded-md
            hover:bg-accent hover:text-accent-foreground ${triggerClassName}`}
      >
        <div className="flex items-center gap-2 truncate">
          {currentValue ? (
            <>
              <AiProviderIcon
                provider={currentValue.providerId}
                className={iconSizeClass}
              />
              {displayIconOnly ? null : (
                <span className="truncate">{displayText}</span>
              )}
            </>
          ) : (
            <span className="text-muted-foreground truncate">
              {placeholder}
            </span>
          )}
        </div>
        <ChevronDownIcon className={`${iconSizeClass} ml-1`} />
      </DropdownMenuTrigger>

      <DropdownMenuContent className="w-[300px]">
        {activeModel &&
          forRole &&
          renderModelWithRole(AiModelId.parse(activeModel), forRole)}
        {activeModel && forRole && <DropdownMenuSeparator />}

        {modelsByProvider.map(([provider, models]) => (
          <ProviderDropdownContent
            key={provider}
            provider={provider}
            onSelect={handleSelect}
            models={models}
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
                href="https://links.marimo.app/custom-models"
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

const ProviderDropdownContent = ({
  provider,
  onSelect,
  models,
  iconSizeClass,
}: {
  provider: ProviderId;
  onSelect: (modelId: QualifiedModelId) => void;
  models: AiModel[];
  iconSizeClass: string;
}) => {
  const iconProvider = isKnownAIProvider(provider)
    ? provider
    : "openai-compatible";

  const maybeProviderInfo = AiModelRegistry.getProviderInfo(provider);

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
        <DropdownMenuSubContent
          className="max-h-[40vh] overflow-y-auto"
          alignOffset={maybeProviderInfo ? -90 : 0}
          sideOffset={5}
        >
          {maybeProviderInfo && (
            <>
              <p className="text-sm text-muted-foreground p-2 max-w-[300px]">
                {maybeProviderInfo.description}
                <br />
              </p>

              <p className="text-sm text-muted-foreground p-2 pt-0">
                For more information, see the{" "}
                <a
                  href={maybeProviderInfo.url}
                  target="_blank"
                  className="underline"
                  rel="noreferrer"
                  aria-label="Provider details"
                >
                  provider details
                </a>
                .
              </p>
              <DropdownMenuSeparator />
            </>
          )}
          {models.map((model) => {
            const qualifiedModelId: QualifiedModelId = `${provider}/${model.model}`;
            return (
              <DropdownMenuSub key={qualifiedModelId}>
                <DropdownMenuSubTrigger showChevron={false} className="py-2">
                  <div
                    className="flex items-center gap-2 w-full cursor-pointer"
                    onClick={() => {
                      onSelect(qualifiedModelId);
                    }}
                  >
                    <AiModelDropdownItem model={model} provider={provider} />
                  </div>
                </DropdownMenuSubTrigger>
                <DropdownMenuSubContent className="p-4 w-80">
                  <AiModelInfoDisplay model={model} provider={provider} />
                </DropdownMenuSubContent>
              </DropdownMenuSub>
            );
          })}
        </DropdownMenuSubContent>
      </DropdownMenuPortal>
    </DropdownMenuSub>
  );
};

const AiModelDropdownItem = ({
  model,
  provider,
}: {
  model: AiModel;
  provider: ProviderId;
}) => {
  const iconProvider = isKnownAIProvider(provider)
    ? provider
    : "openai-compatible";

  return (
    <>
      <AiProviderIcon provider={iconProvider} className="h-4 w-4" />
      <div className="flex flex-row w-full items-center">
        <span>{model.name}</span>
        <div className="ml-auto">
          {model.thinking && (
            <Tooltip content="Reasoning model">
              <BrainIcon
                className={`h-5 w-5 rounded-md p-1 ${getTagColour("thinking")}`}
              />
            </Tooltip>
          )}
        </div>
      </div>
      {model.custom && (
        <Tooltip content="Custom model">
          <BotIcon className="h-5 w-5" />
        </Tooltip>
      )}
    </>
  );
};

export const AiModelInfoDisplay = ({
  model,
  provider,
}: {
  model: AiModel;
  provider: ProviderId;
}) => {
  const ai = useAtomValue(aiAtom);
  const hasInferenceProfiles =
    model.inference_profiles && model.inference_profiles.length > 0;

  // Get the current inference profile for this model
  const inferenceProfiles = ai?.models?.inference_profiles || {};
  const currentProfile =
    (inferenceProfiles[model.model] as string | undefined) || "none";

  // Compute the display model ID with inference profile prefix
  const displayModelId =
    hasInferenceProfiles && currentProfile !== "none"
      ? `${currentProfile}.${model.model}`
      : model.model;

  return (
    <div className="space-y-3">
      <div>
        <h4 className="font-semibold text-base text-foreground">
          {model.name}
        </h4>
        <p className="text-xs text-muted-foreground font-mono">
          {displayModelId}
        </p>
      </div>

      <p className="text-sm text-muted-foreground leading-relaxed">
        {model.description}
      </p>

      {hasInferenceProfiles && currentProfile !== "none" && (
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-1">
            Inference Profile:
          </p>
          <p className="text-xs text-foreground font-mono">{currentProfile}</p>
        </div>
      )}

      {model.roles.length > 0 && (
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2">
            Capabilities:
          </p>
          <div className="flex flex-wrap gap-1">
            {model.roles.map((role) => (
              <span
                key={role}
                className={`px-2 py-1 text-xs rounded-md font-medium ${getTagColour(role)}`}
                title={getCurrentRoleTooltip(role)}
              >
                {role}
              </span>
            ))}
          </div>
        </div>
      )}

      {model.thinking && (
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-purple-500 rounded-full animate-pulse" />
          <span className="text-xs text-muted-foreground">
            Supports thinking mode
          </span>
        </div>
      )}

      <div className="flex items-center gap-2 pt-2 border-t border-border">
        <AiProviderIcon provider={provider} className="h-4 w-4" />
        <span className="text-xs text-muted-foreground">
          {getProviderLabel(provider)}
        </span>
      </div>
    </div>
  );
};

export function getProviderLabel(provider: ProviderId): string {
  const providerInfo = AiModelRegistry.getProviderInfo(provider);
  if (providerInfo) {
    return providerInfo.name;
  }
  return capitalize(provider);
}
