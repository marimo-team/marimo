/* Copyright 2024 Marimo. All rights reserved. */

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

/**
 * AWS Bedrock inference profiles for model IDs
 */
export const AWS_BEDROCK_INFERENCE_PROFILES = [
  { value: "us", label: "US (United States)" },
  { value: "eu", label: "EU (Europe)" },
  { value: "global", label: "Global" },
  { value: "none", label: "No Prefix (Legacy)" },
] as const;
