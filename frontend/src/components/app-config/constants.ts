/* Copyright 2024 Marimo. All rights reserved. */
export const KNOWN_AI_MODELS = [
  // Anthropic
  "claude-opus-4-20250514	",
  "claude-sonnet-4-20250514",
  "claude-3-7-sonnet-latest",
  "claude-3-5-sonnet-latest",
  "claude-3-5-haiku-latest",

  // DeepSeek
  "deepseek-v3",
  "deepseek-r1",

  // Google
  "gemini-2.5-flash-preview-05-20",
  "gemini-2.5-pro-preview-06-05",
  "gemini-2.0-flash",
  "gemini-2.0-flash-lite",

  // OpenAI
  "o3",
  "o4-mini",
  "gpt-4.5-preview",
  "gpt-4.1",
  "gpt-4o",
  "gpt-3.5-turbo",

  // AWS Bedrock Models
  "bedrock/us.anthropic.claude-3-7-sonnet-20250219-v1:0",
  "bedrock/anthropic.claude-3-sonnet-20240229",
  "bedrock/anthropic.claude-3-haiku-20240307",
  "bedrock/meta.llama3-8b-instruct-v1:0",
  "bedrock/amazon.titan-text-express-v1",
  "bedrock/us.amazon.nova-pro-v1:0",
  "bedrock/cohere.command-r-plus-v1",
  "bedrock/ai21.j2-ultra-v1",
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
