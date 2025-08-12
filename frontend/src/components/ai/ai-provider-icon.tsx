/* Copyright 2024 Marimo. All rights reserved. */

import AnthropicIcon from "@marimo-team/llm-info/icons/anthropic.svg?inline";
import BedrockIcon from "@marimo-team/llm-info/icons/aws.svg?inline";
import AzureIcon from "@marimo-team/llm-info/icons/azure.svg?inline";
import GoogleIcon from "@marimo-team/llm-info/icons/google.svg?inline";
import OllamaIcon from "@marimo-team/llm-info/icons/ollama.svg?inline";
import OpenAIIcon from "@marimo-team/llm-info/icons/openai.svg?inline";
import { BotIcon } from "lucide-react";
import * as React from "react";
import { cn } from "@/utils/cn";

const icons = {
  openai: OpenAIIcon,
  anthropic: AnthropicIcon,
  google: GoogleIcon,
  ollama: OllamaIcon,
  azure: AzureIcon,
  bedrock: BedrockIcon,
};

export interface AiProviderIconProps
  extends React.HTMLAttributes<HTMLImageElement> {
  provider: keyof typeof icons | "openai-compatible";
  className?: string;
}

export const AiProviderIcon: React.FC<AiProviderIconProps> = ({
  provider,
  className = "",
  ...props
}) => {
  if (provider === "openai-compatible") {
    return <BotIcon className={cn("h-4 w-4", className)} />;
  }

  const icon = icons[provider];

  return (
    <img
      src={icon}
      alt={provider}
      className={cn("h-4 w-4 grayscale dark:invert", className)}
      {...props}
    />
  );
};
