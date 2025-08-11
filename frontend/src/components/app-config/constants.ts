/* Copyright 2024 Marimo. All rights reserved. */
export const KNOWN_AI_MODELS = [
  // Anthropic
  "anthropic/claude-opus-4-1-20250805",
  "anthropic/claude-opus-4-20250514",
  "anthropic/claude-sonnet-4-20250514",
  "anthropic/claude-3-7-sonnet-latest",
  "anthropic/claude-3-5-sonnet-latest",
  "anthropic/claude-3-5-haiku-latest",

  // DeepSeek
  "deepseek/deepseek-v3",
  "deepseek/deepseek-r1",

  // Google
  "google/gemini-2.5-flash-preview-05-20",
  "google/gemini-2.5-pro-preview-06-05",
  "google/gemini-2.0-flash",
  "google/gemini-2.0-flash-lite",

  // OpenAI
  "openai/o3",
  "openai/o4-mini",
  "openai/gpt-4.5-preview",
  "openai/gpt-4.1",
  "openai/gpt-4o",
  "openai/gpt-3.5-turbo",

  // AWS Bedrock Models
  "bedrock/anthropic.claude-3-5-haiku-20241022-v1:0",
  "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
  "bedrock/anthropic.claude-3-7-sonnet-20250219-v1:0",
  "bedrock/meta.llama3-3-70b-instruct-v1:0",
  "bedrock/cohere.command-r-plus-v1",
] as const;

/**
 * AWS regions where the Bedrock service is available
 */
export const AWS_REGIONS = [
  "us-east-1",
  "us-east-2",
  "us-west-2",
  "eu-central-1",
  "ap-northeast-1",
  "ap-southeast-1",
] as const;
