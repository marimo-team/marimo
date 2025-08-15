/* Copyright 2024 Marimo. All rights reserved. */

import { InfoIcon } from "lucide-react";
import React from "react";
import type { FieldPath, UseFormReturn } from "react-hook-form";
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
import type { QualifiedModelId } from "@/core/ai/ids/ids";
import { CopilotConfig } from "@/core/codemirror/copilot/copilot-config";
import { DEFAULT_AI_MODEL, type UserConfig } from "@/core/config/config-schema";
import { isWasm } from "@/core/wasm/utils";
import { Events } from "@/utils/events";
import { AIModelDropdown } from "../ai/ai-model-dropdown";
import {
  AiProviderIcon,
  type AiProviderIconProps,
} from "../ai/ai-provider-icon";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../ui/accordion";
import { DropdownMenuSeparator } from "../ui/dropdown-menu";
import { ExternalLink } from "../ui/links";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../ui/tabs";
import { Tooltip } from "../ui/tooltip";
import { SettingSubtitle } from "./common";
import { AWS_REGIONS } from "./constants";
import { IncorrectModelId } from "./incorrect-model-id";
import { IsOverridden } from "./is-overridden";

const formItemClasses = "flex flex-row items-center space-x-1 space-y-0";

interface AiConfigProps {
  form: UseFormReturn<UserConfig>;
  config: UserConfig;
  onSubmit: (values: UserConfig) => Promise<void>;
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
  onSubmit: (values: UserConfig) => Promise<void>;
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
  onSubmit: (values: UserConfig) => Promise<void>;
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
      />
    );
  }
};

const SettingGroup = ({ children }: { children: React.ReactNode }) => {
  return <div className="flex flex-col gap-4 pb-4">{children}</div>;
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
            placeholder="ghp_..."
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
            placeholder="https://<your-resource-name>.openai.azure.com"
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

export const AiConfig: React.FC<AiConfigProps> = ({
  form,
  config,
  onSubmit,
}) => {
  return (
    <Tabs defaultValue="ai-features">
      <TabsList className="mb-2">
        <TabsTrigger value="ai-features">AI Features</TabsTrigger>
        <TabsTrigger value="ai-providers">AI Providers</TabsTrigger>
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
    </Tabs>
  );
};
