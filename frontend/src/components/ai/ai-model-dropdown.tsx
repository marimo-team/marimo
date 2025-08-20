/* Copyright 2024 Marimo. All rights reserved. */

import type { Role } from "@marimo-team/llm-info";
import { capitalize } from "lodash-es";
import { ChevronDownIcon, CircleHelpIcon } from "lucide-react";
import {
  AiModelId,
  isKnownAIProvider,
  type ProviderId,
  type QualifiedModelId,
} from "@/core/ai/ids/ids";
import { type AiModel, AiModelRegistry } from "@/core/ai/model-registry";
import { useResolvedMarimoConfig } from "@/core/config/config";
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

interface AIModelDropdownProps {
  value?: string;
  placeholder?: string;
  onSelect: (modelId: QualifiedModelId) => void;
  triggerClassName?: string;
  customDropdownContent?: React.ReactNode;
  iconSize?: "medium" | "small";
  showAddCustomModelDocs?: boolean;
  forRole?: Role;
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
}: AIModelDropdownProps) => {
  const currentValue = value ? AiModelId.parse(value) : undefined;

  const [marimoConfig] = useResolvedMarimoConfig();
  const configModels = marimoConfig.ai?.models;

  // Only include autocompleteModel if copilot is set to "custom"
  const autocompleteModel =
    marimoConfig.completion.copilot === "custom"
      ? configModels?.autocomplete_model
      : undefined;

  const aiModelRegistry = AiModelRegistry.create({
    // We add all the custom models and the models used in the editor.
    // If they among the known models, they won't overwrite them.
    customModels: [
      ...(configModels?.custom_models ?? []),
      configModels?.chat_model,
      autocompleteModel,
      configModels?.edit_model,
    ].filter(Boolean),
    displayedModels: configModels?.displayed_models,
  });
  const modelsByProvider = aiModelRegistry.getGroupedModelsByProvider();

  const activeModel =
    forRole === "autocomplete"
      ? configModels?.autocomplete_model
      : forRole === "chat"
        ? configModels?.chat_model
        : forRole === "edit"
          ? configModels?.edit_model
          : undefined;

  const iconSizeClass = iconSize === "medium" ? "h-4 w-4" : "h-3 w-3";

  const renderModelWithRole = (modelId: AiModelId, role: Role) => {
    const maybeModelMatch = aiModelRegistry.getModel(modelId.id);

    return (
      <div className="flex items-center gap-2 w-full px-2 py-1">
        <AiProviderIcon
          provider={modelId.providerId}
          className={iconSizeClass}
        />
        <div className="flex flex-col">
          <span>{maybeModelMatch?.name || modelId.shortModelId}</span>
          <span className="text-xs text-muted-foreground">{modelId.id}</span>
        </div>

        <div className="ml-auto flex gap-1">
          <span
            key={role}
            className={`text-xs px-1.5 py-0.5 rounded font-medium ${getTagColour(role)}`}
          >
            {role}
          </span>
        </div>
      </div>
    );
  };

  return (
    <DropdownMenu>
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

      <DropdownMenuContent className="w-[300px]">
        {activeModel &&
          forRole &&
          renderModelWithRole(AiModelId.parse(activeModel), forRole)}
        {activeModel && forRole && <DropdownMenuSeparator />}

        {[...modelsByProvider.entries()].map(([provider, models]) => (
          <ProviderDropdownContent
            key={provider}
            provider={provider}
            onSelect={onSelect}
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
  customModelIcon,
  iconSizeClass,
}: {
  provider: ProviderId;
  onSelect: (modelId: QualifiedModelId) => void;
  models: AiModel[];
  customModelIcon?: React.ReactNode;
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
          alignOffset={-90}
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
                <AiProviderIcon provider={iconProvider} className="h-4 w-4" />
                <div className="pl-1 flex flex-col">
                  <span>{model.name}</span>
                  <span className="text-xs text-muted-foreground">
                    {model.model}
                  </span>
                </div>
                {model.custom && customModelIcon}
              </DropdownMenuItem>
            );
          })}
        </DropdownMenuSubContent>
      </DropdownMenuPortal>
    </DropdownMenuSub>
  );
};

function getProviderLabel(provider: ProviderId): string {
  const providerInfo = AiModelRegistry.getProviderInfo(provider);
  if (providerInfo) {
    return providerInfo.name;
  }
  return capitalize(provider);
}

function getTagColour(role: Role): string {
  switch (role) {
    case "chat":
      return "bg-[var(--purple-3)] text-[var(--purple-11)]";
    case "autocomplete":
      return "bg-[var(--green-3)] text-[var(--green-11)]";
    case "edit":
      return "bg-[var(--blue-3)] text-[var(--blue-11)]";
  }
  return "bg-[var(--mauve-3)] text-[var(--mauve-11)]";
}
