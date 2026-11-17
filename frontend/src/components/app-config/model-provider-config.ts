/* Copyright 2026 Marimo. All rights reserved. */

import { omit } from "lodash-es";
import type { UserConfig } from "@/core/config/config-schema";

type AiConfig = NonNullable<UserConfig["ai"]>;
export type ModelProviderConfig = NonNullable<AiConfig["openrouter"]>;

export function getModelProviderConfig(
  ai: UserConfig["ai"],
  providerName: string | null,
): ModelProviderConfig {
  let selected = providerName
    ? ai?.custom_providers?.[providerName]
    : undefined;
  if (!selected && providerName === "openrouter") {
    selected = ai?.openrouter;
  }

  const config = selected ?? {};
  const unsetKeys = Object.entries(config)
    .filter(([, value]) => value === undefined)
    .map(([key]) => key);
  return omit(config, unsetKeys);
}
