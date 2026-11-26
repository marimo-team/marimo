/* Copyright 2026 Marimo. All rights reserved. */
import type { ListSecretKeysResponse } from "@/core/network/types";

type SecretKeyProviders = ListSecretKeysResponse["keys"];

export function filterSecretKeys(
  providers: SecretKeyProviders,
  search: string,
): SecretKeyProviders {
  const query = search.trim().toLowerCase();
  if (!query) {
    return providers;
  }
  return providers
    .map((provider) => ({
      ...provider,
      keys: provider.keys.filter((key) => key.toLowerCase().includes(query)),
    }))
    .filter((provider) => provider.keys.length > 0);
}
