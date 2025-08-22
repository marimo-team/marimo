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
  const [isOpen, setIsOpen] = React.useState(false);

  const ai = useAtomValue(aiAtom);
  const completion = useAtomValue(completionAtom);

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
  });
  const modelsByProvider = aiModelRegistry.getGroupedModelsByProvider();

  const activeModel =
    forRole === "autocomplete"
      ? ai?.models?.autocomplete_model
      : forRole === "chat"
        ? ai?.models?.chat_model
        : forRole === "edit"
          ? ai?.models?.edit_model
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
          <Tooltip content={getTagTooltip(role)}>
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
    onSelect(modelId);
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
            const qualifiedModelId =
              `${provider}/${model.model}` as QualifiedModelId;
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

const AiModelInfoDisplay = ({
  model,
  provider,
}: {
  model: AiModel;
  provider: ProviderId;
}) => {
  return (
    <div className="space-y-3">
      <div>
        <h4 className="font-semibold text-base text-foreground">
          {model.name}
        </h4>
        <p className="text-xs text-muted-foreground font-mono">{model.model}</p>
      </div>

      <p className="text-sm text-muted-foreground leading-relaxed">
        {model.description}
      </p>

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
                title={getTagTooltip(role)}
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

function getProviderLabel(provider: ProviderId): string {
  const providerInfo = AiModelRegistry.getProviderInfo(provider);
  if (providerInfo) {
    return providerInfo.name;
  }
  return capitalize(provider);
}

function getTagColour(role: Role | "thinking"): string {
  switch (role) {
    case "chat":
      return "bg-[var(--purple-3)] text-[var(--purple-11)]";
    case "autocomplete":
      return "bg-[var(--green-3)] text-[var(--green-11)]";
    case "edit":
      return "bg-[var(--blue-3)] text-[var(--blue-11)]";
    case "thinking":
      return "bg-[var(--purple-4)] text-[var(--purple-12)]";
  }
  return "bg-[var(--mauve-3)] text-[var(--mauve-11)]";
}

function getTagTooltip(role: Role): string {
  switch (role) {
    case "chat":
      return "Current model used for chat conversations";
    case "autocomplete":
      return "Current model used for autocomplete autocomplete";
    case "edit":
      return "Current model used for code edits";
    case "rerank":
      return "Current model used for reranking completions";
    case "embed":
      return "Current model used for embedding";
  }
}
