/* Copyright 2026 Marimo. All rights reserved. */

import { createContext, type ReactNode, use, useMemo } from "react";
import { z } from "zod";
import type { FormRenderer } from "@/components/forms/form";
import { FieldOptions } from "@/components/forms/options";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import {
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { SECRETS_REGISTRY } from "@/core/secrets/request-registry";
import { useAsyncData } from "@/hooks/useAsyncData";
import { Functions } from "@/utils/functions";
import {
  sortProviders,
  WriteSecretModal,
} from "../chrome/panels/write-secret-modal";
import { partitionSecretKeys, SecretCombobox } from "./secret-combobox";
import { prefixSecret } from "./secrets";

interface SecretsContextType {
  providerNames: string[];
  secretKeys: string[];
  loading: boolean;
  error: Error | undefined;
  refreshSecrets: () => void;
}

const SecretsContext = createContext<SecretsContextType>({
  providerNames: [],
  secretKeys: [],
  loading: false,
  error: undefined,
  refreshSecrets: Functions.NOOP,
});

export const useSecrets = () => use(SecretsContext);

interface SecretsProviderProps {
  children: ReactNode;
}

export const SecretsProvider = ({ children }: SecretsProviderProps) => {
  const {
    data,
    isPending,
    error,
    refetch: reload,
  } = useAsyncData(async () => {
    const result = await SECRETS_REGISTRY.request({});
    // Provider names without 'env' provider
    const providerNames = sortProviders(result.secrets)
      .filter((provider) => provider.provider !== "env")
      .map((provider) => provider.name);

    return {
      secretKeys: result.secrets.flatMap((secret) => secret.keys).toSorted(),
      providerNames: providerNames,
    };
  }, []);

  const value = useMemo(
    () => ({
      secretKeys: data?.secretKeys || [],
      providerNames: data?.providerNames || [],
      loading: isPending,
      error,
      refreshSecrets: reload,
    }),
    [data?.secretKeys, data?.providerNames, isPending, error, reload],
  );

  return <SecretsContext value={value}>{children}</SecretsContext>;
};

export const ENV_RENDERER: FormRenderer<z.ZodString> = {
  isMatch: (schema: z.ZodType): schema is z.ZodString => {
    if (schema instanceof z.ZodString) {
      const { optionRegex } = FieldOptions.parse(schema.description || "");
      return Boolean(optionRegex);
    }

    return false;
  },
  Component: ({ schema, form, path }) => {
    const { secretKeys, providerNames, refreshSecrets } = useSecrets();
    const { openModal, closeModal } = useImperativeModal();

    const {
      label,
      description,
      placeholder,
      optionRegex = "",
      inputType,
    } = FieldOptions.parse(schema.description || "");

    const secretsOnly = inputType === "password";
    const { recommended, other } = partitionSecretKeys(secretKeys, optionRegex);

    return (
      <FormField
        control={form.control}
        name={path}
        render={({ field }) => (
          <FormItem>
            <FormLabel>{label}</FormLabel>
            <FormDescription>{description}</FormDescription>
            <FormControl>
              <SecretCombobox
                value={field.value ? String(field.value) : ""}
                onChange={field.onChange}
                placeholder={placeholder}
                secretsOnly={secretsOnly}
                recommendedKeys={recommended}
                otherKeys={other}
                onCreateSecret={(suggestedValue) => {
                  openModal(
                    <WriteSecretModal
                      providerNames={providerNames}
                      initialValue={suggestedValue}
                      onSuccess={(secretKey) => {
                        refreshSecrets();
                        field.onChange(prefixSecret(secretKey));
                        closeModal();
                      }}
                      onClose={closeModal}
                    />,
                  );
                }}
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />
    );
  },
};
