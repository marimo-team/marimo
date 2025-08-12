/* Copyright 2024 Marimo. All rights reserved. */

import AnthropicIcon from "@marimo-team/llm-info/icons/anthropic.svg?inline";
import GoogleIcon from "@marimo-team/llm-info/icons/google.svg?inline";
import OllamaIcon from "@marimo-team/llm-info/icons/ollama.svg?inline";
import OpenAIIcon from "@marimo-team/llm-info/icons/openai.svg?inline";
import * as React from "react";
import { cn } from "@/utils/cn";

const icons = {
  openai: OpenAIIcon,
  anthropic: AnthropicIcon,
  google: GoogleIcon,
  ollama: OllamaIcon,
};

export interface AiProviderIconProps
  extends React.HTMLAttributes<HTMLImageElement> {
  provider: keyof typeof icons;
  className?: string;
}

export const AiProviderIcon: React.FC<AiProviderIconProps> = ({
  provider,
  className = "",
  ...props
}) => {
  const icon = icons[provider];

  if (!icon) {
    return null;
  }

  return (
    <img
      src={icon}
      alt={provider}
      className={cn("h-4 w-4", className)}
      {...props}
    />
  );
};
