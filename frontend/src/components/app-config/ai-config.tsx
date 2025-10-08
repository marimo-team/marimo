/* Copyright 2024 Marimo. All rights reserved. */

import {
  BotIcon,
  BrainIcon,
  ChevronRightIcon,
  InfoIcon,
  PlusIcon,
  Trash2Icon,
} from "lucide-react";
import React, { useId, useMemo, useState } from "react";
import {
  Button as AriaButton,
  Tree,
  TreeItem,
  TreeItemContent,
} from "react-aria-components";
import type { FieldPath, UseFormReturn } from "react-hook-form";
import { useWatch } from "react-hook-form";
import useEvent from "react-use-event-hook";
import {
  FormControl,
  FormDescription,
  FormErrorsBanner,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Kbd } from "@/components/ui/kbd";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import type { SupportedRole } from "@/core/ai/config";
import {
  AiModelId,
  PROVIDERS,
  type ProviderId,
  type QualifiedModelId,
  type ShortModelId,
} from "@/core/ai/ids/ids";
import { type AiModel, AiModelRegistry } from "@/core/ai/model-registry";
import { CopilotConfig } from "@/core/codemirror/copilot/copilot-config";
import { DEFAULT_AI_MODEL, type UserConfig } from "@/core/config/config-schema";
import { isWasm } from "@/core/wasm/utils";
import { cn } from "@/utils/cn";
import { Events } from "@/utils/events";
import { Strings } from "@/utils/strings";
import { AIModelDropdown, getProviderLabel } from "../ai/ai-model-dropdown";
import {
  AiProviderIcon,
  type AiProviderIconProps,
} from "../ai/ai-provider-icon";
import { getTagColour } from "../ai/display-helpers";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../ui/accordion";
import { Button } from "../ui/button";
import { Checkbox } from "../ui/checkbox";
import { DropdownMenuSeparator } from "../ui/dropdown-menu";
import { Label } from "../ui/label";
import { ExternalLink } from "../ui/links";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
} from "../ui/select";
import { Switch } from "../ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../ui/tabs";
import { Tooltip } from "../ui/tooltip";
import { SettingSubtitle } from "./common";
import { AWS_REGIONS } from "./constants";
import { IncorrectModelId } from "./incorrect-model-id";
import { IsOverridden } from "./is-overridden";
import { MCPConfig } from "./mcp-config";

const formItemClasses = "flex flex-row items-center space-x-1 space-y-0";

/**
 * Get display label for Bedrock inference profile
 */
function getProfileLabel(profile: string): string {
  const labels: Record<string, string> = {
    us: "US (United States)",
    eu: "EU (Europe)",
    global: "Global",
    "us-gov": "US Gov",
    apac: "APAC (Asia Pacific)",
    jp: "JP (Japan)",
    none: "No Prefix (Legacy)",
  };
  return labels[profile] || profile;
}

interface AiConfigProps {
  form: UseFormReturn<UserConfig>;
  config: UserConfig;
  onSubmit: (values: UserConfig) => void;
}

interface AiProviderTitleProps {
  provider?: AiProviderIconProps["provider"];
  children: React.ReactNode;
}

export const AiProviderTitle: React.FC<AiProviderTitleProps> = ({
  provider,
  children,
}) => {
  return (
    <div className="flex items-center text-base font-semibold">
      {provider && <AiProviderIcon provider={provider} className="mr-2" />}
      {children}
    </div>
  );
};

interface ApiKeyProps {
  form: UseFormReturn<UserConfig>;
  config: UserConfig;
  name: FieldPath<UserConfig>;
  placeholder: string;
  testId: string;
  description?: React.ReactNode;
}

export const ApiKey: React.FC<ApiKeyProps> = ({
  form,
  config,
  name,
  placeholder,
  testId,
  description,
}) => {
  return (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <div className="flex flex-col space-y-1">
          <FormItem className={formItemClasses}>
            <FormLabel>API Key</FormLabel>
            <FormControl>
              <Input
                data-testid={testId}
                rootClassName="flex-1"
                className="m-0 inline-flex h-7"
                placeholder={placeholder}
                {...field}
                value={asStringOrUndefined(field.value)}
                onChange={(e) => {
                  const value = e.target.value;
                  if (!value.includes("*")) {
                    field.onChange(value);
                  }
                }}
              />
            </FormControl>
            <FormMessage />
            <IsOverridden userConfig={config} name={name} />
          </FormItem>
          {description && <FormDescription>{description}</FormDescription>}
        </div>
      )}
    />
  );
};

interface BaseUrlProps {
  form: UseFormReturn<UserConfig>;
  config: UserConfig;
  name: FieldPath<UserConfig>;
  placeholder: string;
  testId: string;
  description?: React.ReactNode;
  disabled?: boolean;
  defaultValue?: string;
}

function asStringOrUndefined<T>(value: T): string | undefined {
  if (value == null) {
    return undefined;
  }

  if (typeof value === "string") {
    return value;
  }

  return String(value);
}

export const BaseUrl: React.FC<BaseUrlProps> = ({
  form,
  config,
  name,
  placeholder,
  testId,
  description,
  disabled = false,
  defaultValue,
}) => {
  return (
    <FormField
      control={form.control}
      name={name}
      disabled={disabled}
      render={({ field }) => (
        <div className="flex flex-col space-y-1">
          <FormItem className={formItemClasses}>
            <FormLabel>Base URL</FormLabel>
            <FormControl>
              <Input
                data-testid={testId}
                rootClassName="flex-1"
                className="m-0 inline-flex h-7"
                placeholder={placeholder}
                defaultValue={defaultValue}
                {...field}
                value={asStringOrUndefined(field.value)}
              />
            </FormControl>
            <FormMessage />
            <IsOverridden userConfig={config} name={name} />
          </FormItem>
          {description && <FormDescription>{description}</FormDescription>}
        </div>
      )}
    />
  );
};

interface ModelSelectorProps {
  form: UseFormReturn<UserConfig>;
  config: UserConfig;
  name: FieldPath<UserConfig>;
  placeholder: string;
  testId: string;
  description?: React.ReactNode;
  disabled?: boolean;
  label: string;
  forRole: SupportedRole;
  onSubmit: (values: UserConfig) => void;
}

export const ModelSelector: React.FC<ModelSelectorProps> = ({
  form,
  config,
  name,
  placeholder,
  testId,
  description,
  disabled = false,
  label,
  forRole,
  onSubmit,
}) => {
  return (
    <FormField
      control={form.control}
      name={name}
      disabled={disabled}
      render={({ field }) => {
        const value = asStringOrUndefined(field.value);

        const selectModel = (modelId: QualifiedModelId) => {
          field.onChange(modelId);
          // Usually not needed, but a hack to force form values to be updated
          onSubmit(form.getValues());
        };

        const renderFormItem = () => (
          <FormItem className={formItemClasses}>
            <FormLabel>{label}</FormLabel>
            <FormControl>
              <AIModelDropdown
                value={value}
                placeholder={placeholder}
                onSelect={selectModel}
                triggerClassName="text-sm"
                customDropdownContent={
                  <>
                    <DropdownMenuSeparator />
                    <p className="px-2 py-1.5 text-sm text-muted-secondary flex items-center gap-1">
                      Enter a custom model
                      <Tooltip content="Models should include the provider prefix, e.g. 'openai/gpt-4o'">
                        <InfoIcon className="h-3 w-3" />
                      </Tooltip>
                    </p>
                    <div className="px-2 py-1">
                      <Input
                        data-testid={testId}
                        className="w-full border-border shadow-none focus-visible:shadow-xs"
                        placeholder={placeholder}
                        {...field}
                        value={asStringOrUndefined(field.value)}
                        onKeyDown={Events.stopPropagation()}
                      />
                      {value && (
                        <IncorrectModelId
                          value={value}
                          includeSuggestion={false}
                        />
                      )}
                    </div>
                  </>
                }
                forRole={forRole}
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        );

        return (
          <div className="flex flex-col space-y-1">
            {renderFormItem()}
            <IsOverridden userConfig={config} name={name} />
            <IncorrectModelId value={value} />
            {description && <FormDescription>{description}</FormDescription>}
          </div>
        );
      }}
    />
  );
};

interface ProviderSelectProps {
  form: UseFormReturn<UserConfig>;
  config: UserConfig;
  name: FieldPath<UserConfig>;
  options: string[];
  testId: string;
  disabled?: boolean;
}

export const ProviderSelect: React.FC<ProviderSelectProps> = ({
  form,
  config,
  name,
  options,
  testId,
  disabled = false,
}) => {
  return (
    <FormField
      control={form.control}
      name={name}
      disabled={disabled}
      render={({ field }) => (
        <div className="flex flex-col space-y-1">
          <FormItem className={formItemClasses}>
            <FormLabel>Provider</FormLabel>
            <FormControl>
              <NativeSelect
                data-testid={testId}
                onChange={(e) => {
                  if (e.target.value === "none") {
                    field.onChange(false);
                  } else {
                    field.onChange(e.target.value);
                  }
                }}
                value={asStringOrUndefined(
                  field.value === true
                    ? "github"
                    : field.value === false
                      ? "none"
                      : field.value,
                )}
                disabled={field.disabled}
                className="inline-flex mr-2"
              >
                {options.map((option) => (
                  <option value={option} key={option}>
                    {option}
                  </option>
                ))}
              </NativeSelect>
            </FormControl>
            <FormMessage />
            <IsOverridden userConfig={config} name={name} />
          </FormItem>
        </div>
      )}
    />
  );
};

const renderCopilotProvider = ({
  form,
  config,
  onSubmit,
}: {
  form: UseFormReturn<UserConfig>;
  config: UserConfig;
  onSubmit: (values: UserConfig) => void;
}) => {
  const copilot = form.getValues("completion.copilot");
  if (copilot === false) {
    return null;
  }

  if (copilot === "codeium") {
    return (
      <>
        <p className="text-sm text-muted-secondary">
          To get a Windsurf API key, follow{" "}
          <ExternalLink href="https://docs.marimo.io/guides/editor_features/ai_completion.html#windsurf-copilot">
            these instructions
          </ExternalLink>
          .
        </p>
        <ApiKey
          form={form}
          config={config}
          name="completion.codeium_api_key"
          placeholder="key"
          testId="codeium-api-key-input"
        />
      </>
    );
  }

  if (copilot === "github") {
    return <CopilotConfig />;
  }

  if (copilot === "custom") {
    return (
      <ModelSelector
        label="Autocomplete Model"
        form={form}
        config={config}
        name="ai.models.autocomplete_model"
        placeholder="ollama/qwen2.5-coder:1.5b"
        testId="custom-model-input"
        description="Model to use for code completion when using a custom provider."
        onSubmit={onSubmit}
        forRole="autocomplete"
      />
    );
  }
};

const SettingGroup = ({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) => {
  return (
    <div className={cn("flex flex-col gap-4 pb-4", className)}>{children}</div>
  );
};

interface ModelListItemProps {
  qualifiedId: QualifiedModelId;
  model: AiModel;
  isEnabled: boolean;
  onToggle: (modelId: QualifiedModelId) => void;
  onDelete: (modelId: QualifiedModelId) => void;
  form?: UseFormReturn<UserConfig>;
  onSubmit?: (values: UserConfig) => void;
}

const ModelListItem: React.FC<ModelListItemProps> = ({
  qualifiedId,
  model,
  isEnabled,
  onToggle,
  onDelete,
  form,
  onSubmit,
}) => {
  const handleToggle = () => {
    onToggle(qualifiedId);
  };

  const handleDelete = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    e.preventDefault();
    onDelete(qualifiedId);
  };

  return (
    <TreeItem
      id={qualifiedId}
      textValue={model.name}
      className="pl-6 outline-none data-focused:bg-muted/50 hover:bg-muted/50"
      onAction={handleToggle}
    >
      <TreeItemContent>
        <div className="flex items-center justify-between px-4 py-3 border-b last:border-b-0 cursor-pointer outline-none">
          <ModelInfoCard
            model={model}
            qualifiedId={qualifiedId}
            form={form}
            onSubmit={onSubmit}
          />
          {model.custom && (
            <Button
              variant="ghost"
              size="icon"
              onClick={handleDelete}
              className="mr-2 hover:bg-transparent"
            >
              <Trash2Icon className="h-3.5 w-3.5 text-muted-foreground" />
            </Button>
          )}
          <Switch checked={isEnabled} onClick={handleToggle} size="sm" />
        </div>
      </TreeItemContent>
    </TreeItem>
  );
};

const ModelInfoCard = ({
  model,
  qualifiedId,
  form,
  onSubmit,
}: {
  model: AiModel;
  qualifiedId: QualifiedModelId;
  form?: UseFormReturn<UserConfig>;
  onSubmit?: (values: UserConfig) => void;
}) => {
  const modelId = AiModelId.parse(qualifiedId);
  const hasInferenceProfiles =
    model.inference_profiles && model.inference_profiles.length > 0;

  // Get the current inference profile for this model
  const aiModels = form
    ? useWatch({
        control: form.control,
        name: "ai.models",
      })
    : undefined;

  const inferenceProfiles = aiModels?.bedrock_inference_profiles || {};

  const currentProfile =
    (inferenceProfiles[model.model] as string | undefined) || "none";

  // Compute the display model ID with inference profile prefix
  const displayModelId =
    hasInferenceProfiles && currentProfile !== "none"
      ? `${modelId.providerId}/${currentProfile}.${model.model}`
      : qualifiedId;

  const handleProfileChange = (newProfile: string) => {
    if (!form || !onSubmit) {
      return;
    }

    const updatedProfiles = { ...inferenceProfiles };
    if (newProfile === "none") {
      delete updatedProfiles[model.model];
    } else {
      updatedProfiles[model.model] = newProfile as
        | "us"
        | "eu"
        | "global"
        | "none";
    }

    const currentModels = form.getValues("ai.models");
    if (currentModels) {
      form.setValue("ai.models", {
        ...currentModels,
        bedrock_inference_profiles: updatedProfiles,
      });
      onSubmit(form.getValues());
    }
  };

  return (
    <div className="flex items-center gap-3 flex-1">
      <div className="flex flex-col flex-1">
        <div className="flex items-center gap-2">
          <h3 className="font-medium">{model.name}</h3>
          <Tooltip content="Custom model">
            {model.custom && <BotIcon className="h-4 w-4" />}
          </Tooltip>
        </div>
        <span className="text-xs text-muted-foreground font-mono">
          {displayModelId}
        </span>
        {model.description && !model.custom && (
          <p className="text-sm text-muted-secondary mt-1 line-clamp-2">
            {model.description}
          </p>
        )}

        {hasInferenceProfiles && form && onSubmit && (
          <div className="flex items-center gap-2 mt-2">
            <Label className="text-xs font-medium text-muted-foreground">
              Inference Profile:
            </Label>
            <NativeSelect
              value={currentProfile}
              onChange={(e) => handleProfileChange(e.target.value)}
              className="text-xs h-7"
              onClick={Events.stopPropagation()}
            >
              <option value="none" key="none">
                {getProfileLabel("none")}
              </option>
              {model.inference_profiles!.map((profile) => (
                <option value={profile} key={profile}>
                  {getProfileLabel(profile)}
                </option>
              ))}
            </NativeSelect>
          </div>
        )}

        {model.thinking && (
          <div
            className={cn(
              "flex items-center gap-1 rounded px-1 py-0.5 w-fit mt-1.5",
              getTagColour("thinking"),
            )}
          >
            <BrainIcon className="h-3 w-3" />
            <span className="text-xs font-medium">Reasoning</span>
          </div>
        )}
      </div>
    </div>
  );
};

export const AiCodeCompletionConfig: React.FC<AiConfigProps> = ({
  form,
  config,
  onSubmit,
}) => {
  return (
    <SettingGroup>
      <SettingSubtitle>Code Completion</SettingSubtitle>
      <p className="text-sm text-muted-secondary">
        Choose GitHub Copilot, Codeium, or a custom provider (such as Ollama) to
        enable AI-powered code completion.
      </p>

      <ProviderSelect
        form={form}
        config={config}
        name="completion.copilot"
        options={["none", "github", "codeium", "custom"]}
        testId="copilot-select"
      />

      {renderCopilotProvider({ form, config, onSubmit })}
    </SettingGroup>
  );
};

const AccordionFormItem = ({
  title,
  triggerClassName,
  provider,
  children,
  isConfigured,
}: {
  title: string;
  triggerClassName?: string;
  provider: AiProviderIconProps["provider"];
  children: React.ReactNode;
  isConfigured: boolean;
}) => {
  return (
    <AccordionItem value={provider}>
      <AccordionTrigger className={triggerClassName}>
        <AiProviderTitle provider={provider}>
          {title}
          {isConfigured && (
            <span className="ml-2 px-1 rounded bg-muted text-xs font-medium border">
              Configured
            </span>
          )}
        </AiProviderTitle>
      </AccordionTrigger>
      <AccordionContent wrapperClassName="flex flex-col gap-4">
        {children}
      </AccordionContent>
    </AccordionItem>
  );
};

export const AiProvidersConfig: React.FC<AiConfigProps> = ({
  form,
  config,
}) => {
  const isWasmRuntime = isWasm();

  const hasValue = (name: FieldPath<UserConfig>) => {
    return !!form.getValues(name);
  };

  return (
    <SettingGroup>
      <p className="text-sm text-muted-secondary">
        Add your API keys below or to <Kbd className="inline">marimo.toml</Kbd>{" "}
        to set up a provider for the Code Completion and Assistant features; see{" "}
        <ExternalLink href="https://docs.marimo.io/guides/editor_features/ai_completion/#connecting-to-an-llm">
          docs
        </ExternalLink>{" "}
        for more info.
      </p>
      <Accordion type="multiple">
        <AccordionFormItem
          title="OpenAI"
          provider="openai"
          triggerClassName="pt-0"
          isConfigured={hasValue("ai.open_ai.api_key")}
        >
          <ApiKey
            form={form}
            config={config}
            name="ai.open_ai.api_key"
            placeholder="sk-proj..."
            testId="ai-openai-api-key-input"
            description={
              <>
                Your OpenAI API key from{" "}
                <ExternalLink href="https://platform.openai.com/account/api-keys">
                  platform.openai.com
                </ExternalLink>
                .
              </>
            }
          />
          <BaseUrl
            form={form}
            config={config}
            name="ai.open_ai.base_url"
            placeholder="https://api.openai.com/v1"
            testId="ai-base-url-input"
            disabled={isWasmRuntime}
          />
        </AccordionFormItem>

        <AccordionFormItem
          title="Anthropic"
          provider="anthropic"
          isConfigured={hasValue("ai.anthropic.api_key")}
        >
          <ApiKey
            form={form}
            config={config}
            name="ai.anthropic.api_key"
            placeholder="sk-ant..."
            testId="ai-anthropic-api-key-input"
            description={
              <>
                Your Anthropic API key from{" "}
                <ExternalLink href="https://console.anthropic.com/settings/keys">
                  console.anthropic.com
                </ExternalLink>
                .
              </>
            }
          />
        </AccordionFormItem>

        <AccordionFormItem
          title="Google"
          provider="google"
          isConfigured={hasValue("ai.google.api_key")}
        >
          <ApiKey
            form={form}
            config={config}
            name="ai.google.api_key"
            placeholder="AI..."
            testId="ai-google-api-key-input"
            description={
              <>
                Your Google AI API key from{" "}
                <ExternalLink href="https://aistudio.google.com/app/apikey">
                  aistudio.google.com
                </ExternalLink>
                .
              </>
            }
          />
        </AccordionFormItem>

        <AccordionFormItem
          title="Ollama"
          provider="ollama"
          isConfigured={hasValue("ai.ollama.base_url")}
        >
          <BaseUrl
            form={form}
            config={config}
            name="ai.ollama.base_url"
            placeholder="http://localhost:11434/v1"
            defaultValue="http://localhost:11434/v1"
            testId="ollama-base-url-input"
          />
        </AccordionFormItem>

        <AccordionFormItem
          title="GitHub"
          provider="github"
          isConfigured={hasValue("ai.github.api_key")}
        >
          <ApiKey
            form={form}
            config={config}
            name="ai.github.api_key"
            placeholder="gho_..."
            testId="ai-github-api-key-input"
            description={
              <>
                Your GitHub API token from{" "}
                <Kbd className="inline">gh auth token</Kbd>.
              </>
            }
          />
          <BaseUrl
            form={form}
            config={config}
            name="ai.github.base_url"
            placeholder="https://api.githubcopilot.com/"
            testId="ai-github-base-url-input"
          />
        </AccordionFormItem>

        <AccordionFormItem
          title="OpenRouter"
          provider="openrouter"
          isConfigured={hasValue("ai.openrouter.api_key")}
        >
          <ApiKey
            form={form}
            config={config}
            name="ai.openrouter.api_key"
            placeholder="or-..."
            testId="ai-openrouter-api-key-input"
            description={
              <>
                Your OpenRouter API key from {""}
                <ExternalLink href="https://openrouter.ai/keys">
                  openrouter.ai
                </ExternalLink>
                .
              </>
            }
          />
          <BaseUrl
            form={form}
            config={config}
            name="ai.openrouter.base_url"
            placeholder="https://openrouter.ai/api/v1/"
            testId="ai-openrouter-base-url-input"
          />
        </AccordionFormItem>

        <AccordionFormItem
          title="Azure"
          provider="azure"
          isConfigured={
            hasValue("ai.azure.api_key") && hasValue("ai.azure.base_url")
          }
        >
          <ApiKey
            form={form}
            config={config}
            name="ai.azure.api_key"
            placeholder="sk-proj..."
            testId="ai-azure-api-key-input"
            description={
              <>
                Your Azure API key from{" "}
                <ExternalLink href="https://portal.azure.com/">
                  portal.azure.com
                </ExternalLink>
                .
              </>
            }
          />
          <BaseUrl
            form={form}
            config={config}
            name="ai.azure.base_url"
            placeholder="https://<your-resource-name>.openai.azure.com/openai/deployments/<deployment-name>?api-version=<api-version>"
            defaultValue="https://<your-resource-name>.openai.azure.com/openai/deployments/<deployment-name>?api-version=<api-version>"
            testId="ai-azure-base-url-input"
          />
        </AccordionFormItem>

        <AccordionFormItem
          title="AWS Bedrock"
          provider="bedrock"
          isConfigured={hasValue("ai.bedrock.region_name")}
        >
          <p className="text-sm text-muted-secondary mb-2">
            To use AWS Bedrock, you need to configure AWS credentials and
            region. See the{" "}
            <ExternalLink href="https://docs.marimo.io/guides/editor_features/ai_completion.html#aws-bedrock">
              documentation
            </ExternalLink>{" "}
            for more details.
          </p>

          <FormField
            control={form.control}
            disabled={isWasmRuntime}
            name="ai.bedrock.region_name"
            render={({ field }) => (
              <div className="flex flex-col space-y-1">
                <FormItem className={formItemClasses}>
                  <FormLabel>AWS Region</FormLabel>
                  <FormControl>
                    <NativeSelect
                      data-testid="bedrock-region-select"
                      onChange={(e) => field.onChange(e.target.value)}
                      value={
                        typeof field.value === "string"
                          ? field.value
                          : "us-east-1"
                      }
                      disabled={field.disabled}
                      className="inline-flex mr-2"
                    >
                      {AWS_REGIONS.map((option) => (
                        <option value={option} key={option}>
                          {option}
                        </option>
                      ))}
                    </NativeSelect>
                  </FormControl>
                  <FormMessage />
                  <IsOverridden
                    userConfig={config}
                    name="ai.bedrock.region_name"
                  />
                </FormItem>
                <FormDescription>
                  The AWS region where Bedrock service is available.
                </FormDescription>
              </div>
            )}
          />

          <FormField
            control={form.control}
            disabled={isWasmRuntime}
            name="ai.bedrock.profile_name"
            render={({ field }) => (
              <div className="flex flex-col space-y-1">
                <FormItem className={formItemClasses}>
                  <FormLabel>AWS Profile Name (Optional)</FormLabel>
                  <FormControl>
                    <Input
                      data-testid="bedrock-profile-input"
                      rootClassName="flex-1"
                      className="m-0 inline-flex h-7"
                      placeholder="default"
                      {...field}
                      value={field.value || ""}
                    />
                  </FormControl>
                  <FormMessage />
                  <IsOverridden
                    userConfig={config}
                    name="ai.bedrock.profile_name"
                  />
                </FormItem>
                <FormDescription>
                  The AWS profile name from your ~/.aws/credentials file. Leave
                  blank to use your default AWS credentials.
                </FormDescription>
              </div>
            )}
          />
        </AccordionFormItem>

        <AccordionFormItem
          title="OpenAI-Compatible"
          provider="openai-compatible"
          isConfigured={
            hasValue("ai.open_ai_compatible.api_key") &&
            hasValue("ai.open_ai_compatible.base_url")
          }
        >
          <ApiKey
            form={form}
            config={config}
            name="ai.open_ai_compatible.api_key"
            placeholder="sk-..."
            testId="ai-openai-compatible-api-key-input"
            description={
              <>
                API key for any OpenAI-compatible provider (e.g., Together,
                Groq, Mistral, Perplexity, etc).
              </>
            }
          />
          <BaseUrl
            form={form}
            config={config}
            name="ai.open_ai_compatible.base_url"
            placeholder="https://api.together.xyz/v1"
            testId="ai-openai-compatible-base-url-input"
            description={<>Base URL for your OpenAI-compatible provider.</>}
          />
        </AccordionFormItem>
      </Accordion>
    </SettingGroup>
  );
};

export const AiAssistConfig: React.FC<AiConfigProps> = ({
  form,
  config,
  onSubmit,
}) => {
  const isWasmRuntime = isWasm();

  return (
    <SettingGroup>
      <SettingSubtitle>AI Assistant</SettingSubtitle>

      <FormField
        control={form.control}
        name="ai.inline_tooltip"
        render={({ field }) => (
          <div className="flex flex-col gap-y-1">
            <FormItem className={formItemClasses}>
              <FormLabel className="font-normal">AI Edit Tooltip</FormLabel>
              <FormControl>
                <Checkbox
                  data-testid="inline-ai-checkbox"
                  checked={field.value === true}
                  onCheckedChange={field.onChange}
                />
              </FormControl>
            </FormItem>
            <FormDescription>
              Enable "Edit with AI" tooltip when selecting code.
            </FormDescription>
          </div>
        )}
      />

      <FormErrorsBanner />
      <ModelSelector
        label="Chat Model"
        form={form}
        config={config}
        name="ai.models.chat_model"
        placeholder={DEFAULT_AI_MODEL}
        testId="ai-chat-model-input"
        disabled={isWasmRuntime}
        description={
          <span>Model to use for chat conversations in the Chat panel.</span>
        }
        forRole="chat"
        onSubmit={onSubmit}
      />
      <ModelSelector
        label="Edit Model"
        form={form}
        config={config}
        name="ai.models.edit_model"
        placeholder={DEFAULT_AI_MODEL}
        testId="ai-edit-model-input"
        disabled={isWasmRuntime}
        description={
          <span>
            Model to use for code editing with the{" "}
            <Kbd className="inline">Generate with AI</Kbd> button.
          </span>
        }
        forRole="edit"
        onSubmit={onSubmit}
      />

      <ul className="bg-muted p-2 rounded-md list-disc space-y-1 pl-6">
        <li className="text-xs text-muted-secondary">
          Models should include the provider name and model name separated by a
          slash. For example, "anthropic/claude-3-5-sonnet-latest" or
          "google/gemini-2.0-flash-exp"
        </li>
        <li className="text-xs text-muted-secondary">
          Depending on the provider, we will use the respective API key and
          additional configuration.
        </li>
      </ul>

      <FormField
        control={form.control}
        name="ai.rules"
        render={({ field }) => (
          <div className="flex flex-col">
            <FormItem>
              <FormLabel>Custom Rules</FormLabel>
              <FormControl>
                <Textarea
                  data-testid="ai-rules-input"
                  className="m-0 inline-flex w-full h-32 p-2 text-sm"
                  placeholder="e.g. Always use type hints; prefer polars over pandas"
                  {...field}
                  value={field.value}
                />
              </FormControl>
              <FormMessage />
              <IsOverridden userConfig={config} name="ai.rules" />
            </FormItem>
            <FormDescription>
              Custom rules to include in all AI completion prompts.
            </FormDescription>
          </div>
        )}
      />
    </SettingGroup>
  );
};

interface ProviderTreeItemProps {
  providerId: ProviderId;
  models: AiModel[];
  enabledModels: Set<QualifiedModelId>;
  onToggleModel: (modelId: QualifiedModelId) => void;
  onToggleProvider: (providerId: ProviderId, enable: boolean) => void;
  onDeleteModel: (modelId: QualifiedModelId) => void;
  form?: UseFormReturn<UserConfig>;
  onSubmit?: (values: UserConfig) => void;
}

const ProviderTreeItem: React.FC<ProviderTreeItemProps> = ({
  providerId,
  models,
  enabledModels,
  onToggleModel,
  onToggleProvider,
  onDeleteModel,
  form,
  onSubmit,
}) => {
  const enabledCount = models.filter((model) =>
    enabledModels.has(new AiModelId(providerId, model.model).id),
  ).length;
  const totalCount = models.length;
  const maybeProviderInfo = AiModelRegistry.getProviderInfo(providerId);
  const name = maybeProviderInfo?.name || Strings.startCase(providerId);

  const checkboxState =
    enabledCount === 0
      ? false
      : enabledCount === totalCount
        ? true
        : "indeterminate";

  const handleProviderToggle = useEvent(() => {
    const shouldEnable = enabledCount < totalCount / 2;
    onToggleProvider(providerId, shouldEnable);
  });

  return (
    <TreeItem
      id={providerId}
      hasChildItems={true}
      textValue={providerId}
      className="outline-none data-focused:bg-muted/50 group"
    >
      <TreeItemContent>
        <div className="flex items-center gap-3 px-3 py-3 hover:bg-muted/50 cursor-pointer outline-none focus-visible:outline-none">
          <Checkbox
            checked={checkboxState}
            onCheckedChange={handleProviderToggle}
            onClick={Events.stopPropagation()}
          />
          <AiProviderIcon provider={providerId} className="h-5 w-5" />
          <div className="flex items-center justify-between w-full">
            <h2 className="font-semibold">{name}</h2>
            <p className="text-sm text-muted-secondary">
              {enabledCount}/{totalCount} models
            </p>
          </div>
          <AriaButton slot="chevron">
            <ChevronRightIcon className="h-4 w-4 text-muted-foreground shrink-0 transition-transform duration-200 group-data-[expanded]:rotate-90" />
          </AriaButton>
        </div>
      </TreeItemContent>

      {models.map((model) => {
        const qualifiedId = new AiModelId(providerId, model.model).id;
        return (
          <ModelListItem
            key={qualifiedId}
            qualifiedId={qualifiedId}
            model={model}
            isEnabled={enabledModels.has(qualifiedId)}
            onToggle={onToggleModel}
            onDelete={onDeleteModel}
            form={form}
            onSubmit={onSubmit}
          />
        );
      })}
    </TreeItem>
  );
};

export const AiModelDisplayConfig: React.FC<AiConfigProps> = ({
  form,
  onSubmit,
}) => {
  const customModels = useWatch({
    control: form.control,
    name: "ai.models.custom_models",
  }) as QualifiedModelId[];

  const inferenceProfiles = useWatch({
    control: form.control,
    name: "ai.models.bedrock_inference_profiles",
  }) as Record<string, string> | undefined;

  const aiModelRegistry = useMemo(
    () =>
      AiModelRegistry.create({
        displayedModels: [],
        customModels: customModels,
        inferenceProfiles: inferenceProfiles || {},
      }),
    [customModels, inferenceProfiles],
  );
  const currentDisplayedModels = useWatch({
    control: form.control,
    name: "ai.models.displayed_models",
    defaultValue: [],
  }) as QualifiedModelId[];
  const currentDisplayedModelsSet = new Set(currentDisplayedModels);
  const modelsByProvider = aiModelRegistry.getGroupedModelsByProvider();
  const listModelsByProvider = aiModelRegistry.getListModelsByProvider();

  const toggleModelDisplay = useEvent((modelId: QualifiedModelId) => {
    const newModels = currentDisplayedModelsSet.has(modelId)
      ? currentDisplayedModels.filter((id) => id !== modelId)
      : [...currentDisplayedModels, modelId];

    form.setValue("ai.models.displayed_models", newModels);
    onSubmit(form.getValues());
  });

  const toggleProviderModels = useEvent(
    async (providerId: ProviderId, enable: boolean) => {
      const providerModels = modelsByProvider.get(providerId) || [];
      const qualifiedModelIds = new Set(
        providerModels.map((m) => new AiModelId(providerId, m.model).id),
      );

      // If enabled, we add all provider models that aren't already enabled
      // Else, remove all provider models
      const newModels: QualifiedModelId[] = enable
        ? [...new Set([...currentDisplayedModels, ...qualifiedModelIds])]
        : currentDisplayedModels.filter((id) => !qualifiedModelIds.has(id));

      form.setValue("ai.models.displayed_models", newModels);
      onSubmit(form.getValues());
    },
  );

  const deleteModel = useEvent((modelId: QualifiedModelId) => {
    const newModels = customModels.filter((id) => id !== modelId);
    form.setValue("ai.models.custom_models", newModels);
    onSubmit(form.getValues());
  });

  return (
    <SettingGroup className="gap-2">
      <p className="text-sm text-muted-secondary mb-6">
        Control which AI models are displayed in model selection dropdowns. When
        no models are selected, all available models will be shown.
      </p>

      <div className="border rounded-md bg-background">
        <Tree
          aria-label="AI Models by Provider"
          className="flex-1 overflow-auto outline-none focus-visible:outline-none"
          selectionMode="none"
        >
          {listModelsByProvider.map(([providerId, models]) => (
            <ProviderTreeItem
              key={providerId}
              providerId={providerId}
              models={models}
              enabledModels={currentDisplayedModelsSet}
              onToggleModel={toggleModelDisplay}
              onToggleProvider={toggleProviderModels}
              onDeleteModel={deleteModel}
              form={form}
              onSubmit={onSubmit}
            />
          ))}
        </Tree>
      </div>
      <AddModelForm
        form={form}
        customModels={customModels}
        onSubmit={onSubmit}
      />
    </SettingGroup>
  );
};

export const AddModelForm: React.FC<{
  form: UseFormReturn<UserConfig>;
  customModels: QualifiedModelId[];
  onSubmit: (values: UserConfig) => void;
}> = ({ form, customModels, onSubmit }) => {
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [modelAdded, setModelAdded] = useState(false);
  const [provider, setProvider] = useState<ProviderId | "custom" | null>(null);
  const [customProviderName, setCustomProviderName] = useState("");
  const [modelName, setModelName] = useState("");

  const providerSelectId = useId();
  const customProviderInputId = useId();
  const modelNameInputId = useId();

  const isCustomProvider = provider === "custom";
  const providerName = isCustomProvider ? customProviderName : provider;
  const hasValidValues = providerName?.trim() && modelName?.trim();

  const resetForm = () => {
    setProvider(null);
    setCustomProviderName("");
    setModelName("");
    setIsFormOpen(false);
  };

  const handleAddModel = () => {
    if (!hasValidValues) {
      return;
    }

    const newModel = new AiModelId(
      providerName as ProviderId,
      modelName as ShortModelId,
    );

    form.setValue("ai.models.custom_models", [newModel.id, ...customModels]);
    onSubmit(form.getValues());
    resetForm();

    // Show model added message for 2 seconds
    setModelAdded(true);
    setTimeout(() => setModelAdded(false), 2000);
  };

  const providerClassName = "w-40 truncate";

  const providerSelect = (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <Label
          htmlFor={providerSelectId}
          className="text-sm font-medium text-muted-foreground min-w-12"
        >
          Provider
        </Label>
        <Select
          value={provider || ""}
          onValueChange={(v) => setProvider(v as ProviderId | "custom")}
        >
          <SelectTrigger id={providerSelectId} className={providerClassName}>
            {provider ? (
              <div className="flex items-center gap-1.5">
                <AiProviderIcon
                  provider={provider as ProviderId}
                  className="h-3.5 w-3.5"
                />
                <span>{getProviderLabel(provider as ProviderId)}</span>
              </div>
            ) : (
              <span className="text-muted-foreground">Select...</span>
            )}
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem value="custom">
                <div className="flex items-center gap-2">
                  <AiProviderIcon
                    provider="openai-compatible"
                    className="h-4 w-4"
                  />
                  <span>Custom</span>
                </div>
              </SelectItem>
              {PROVIDERS.filter((p) => p !== "marimo").map((p) => (
                <SelectItem key={p} value={p}>
                  <div className="flex items-center gap-2">
                    <AiProviderIcon provider={p} className="h-4 w-4" />
                    <span>{getProviderLabel(p)}</span>
                  </div>
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      </div>

      {isCustomProvider && (
        <div className="flex items-center gap-2">
          <Label
            htmlFor={customProviderInputId}
            className="text-sm font-medium text-muted-foreground min-w-12"
          >
            Name
          </Label>
          <Input
            id={customProviderInputId}
            value={customProviderName}
            onChange={(e) => setCustomProviderName(e.target.value)}
            placeholder="openrouter"
            className={providerClassName}
          />
        </div>
      )}
    </div>
  );

  const modelInput = (
    <div
      className={cn(
        "flex items-center gap-2",
        isCustomProvider && "self-start",
      )}
    >
      <Label
        htmlFor={modelNameInputId}
        className="text-sm font-medium text-muted-foreground"
      >
        Model
      </Label>
      <Input
        id={modelNameInputId}
        value={modelName}
        onChange={(e) => setModelName(e.target.value)}
        placeholder="gpt-4"
        className="text-xs mb-0"
      />
    </div>
  );

  const inputForm = (
    <div className="flex items-center gap-3 p-3 border border-border rounded-md">
      {providerSelect}
      {modelInput}
      <div
        className={cn("flex gap-1.5 ml-auto", isCustomProvider && "self-end")}
      >
        <Button onClick={handleAddModel} disabled={!hasValidValues} size="xs">
          Add
        </Button>
        <Button variant="outline" onClick={resetForm} size="xs">
          Cancel
        </Button>
      </div>
    </div>
  );

  return (
    <div>
      {isFormOpen && inputForm}
      <div className="flex flex-row text-sm">
        <Button
          onClick={(e) => {
            e.preventDefault();
            setIsFormOpen(true);
          }}
          variant="link"
          disabled={isFormOpen}
        >
          <PlusIcon className="h-4 w-4 mr-2 mb-0.5" />
          Add Model
        </Button>
        {modelAdded && (
          <div className="flex items-center gap-1 text-green-700 bg-green-500/10 px-2 py-1 rounded-md ml-auto">
            ✓ Model added
          </div>
        )}
      </div>
    </div>
  );
};

export const AiConfig: React.FC<AiConfigProps> = ({
  form,
  config,
  onSubmit,
}) => {
  // MCP is not supported in WASM
  const wasm = isWasm();
  return (
    <Tabs defaultValue="ai-features" className="flex-1">
      <TabsList className="mb-2">
        <TabsTrigger value="ai-features">AI Features</TabsTrigger>
        <TabsTrigger value="ai-providers">AI Providers</TabsTrigger>
        <TabsTrigger value="ai-models">AI Models</TabsTrigger>
        {!wasm && <TabsTrigger value="mcp">MCP</TabsTrigger>}
      </TabsList>

      <TabsContent value="ai-features">
        <AiCodeCompletionConfig
          form={form}
          config={config}
          onSubmit={onSubmit}
        />
        <AiAssistConfig form={form} config={config} onSubmit={onSubmit} />
      </TabsContent>
      <TabsContent value="ai-providers">
        <AiProvidersConfig form={form} config={config} onSubmit={onSubmit} />
      </TabsContent>
      <TabsContent value="ai-models">
        <AiModelDisplayConfig form={form} config={config} onSubmit={onSubmit} />
      </TabsContent>
      {!wasm && (
        <TabsContent value="mcp">
          <MCPConfig form={form} onSubmit={onSubmit} />
        </TabsContent>
      )}
    </Tabs>
  );
};
