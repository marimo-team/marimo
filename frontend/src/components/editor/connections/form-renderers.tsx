/* Copyright 2026 Marimo. All rights reserved. */

import { InfoIcon } from "lucide-react";
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
import { Tooltip } from "@/components/ui/tooltip";
import { SECRETS_REGISTRY } from "@/core/secrets/request-registry";
import { useAsyncData } from "@/hooks/useAsyncData";
import { Functions } from "@/utils/functions";
import {
  sortProviders,
  WriteSecretModal,
} from "../chrome/panels/write-secret-modal";
import { looksLikeJson } from "./json-credentials";
import { isPath, prefixPath, unprefixPath } from "./paths";
import { partitionSecretKeys, SecretCombobox } from "./secret-combobox";
import { isSecret, prefixSecret } from "./secrets";

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

/**
 * For credentials that shouldn't be baked into the generated notebook code
 * (e.g. a service-account JSON key).
 */
export const SECRET_TEXTAREA_RENDERER: FormRenderer<z.ZodString> = {
  isMatch: (schema: z.ZodType): schema is z.ZodString => {
    if (schema instanceof z.ZodString) {
      const { special } = FieldOptions.parse(schema.description || "");
      return special === "secret_textarea";
    }
    return false;
  },
  Component: ({ schema, form, path }) => {
    const { secretKeys, providerNames, refreshSecrets } = useSecrets();
    const { openModal, closeModal } = useImperativeModal();
    const { label, description, placeholder } = FieldOptions.parse(
      schema.description || "",
    );

    return (
      <FormField
        control={form.control}
        name={path}
        render={({ field }) => {
          const value = field.value ? String(field.value) : "";
          // Non-secret values are file paths; display them unprefixed.
          const displayValue = isPath(value) ? unprefixPath(value) : value;

          return (
            <FormItem>
              <FormLabel className="flex items-center gap-1">
                {label}
                <Tooltip
                  content="Enter a path to a file on disk, or create a secret to paste JSON directly."
                  delayDuration={300}
                >
                  <span className="inline-flex" tabIndex={0}>
                    <InfoIcon className="h-3.5 w-3.5" />
                  </span>
                </Tooltip>
              </FormLabel>
              <FormDescription>{description}</FormDescription>
              <FormControl>
                <SecretCombobox
                  value={displayValue}
                  onChange={(next) => {
                    field.onChange(
                      !next || isSecret(next) ? next : prefixPath(next),
                    );
                  }}
                  placeholder={placeholder}
                  searchPlaceholder="Type a file path or paste JSON"
                  formatCustomValueLabel={(custom) =>
                    `Use "${custom}" as a file path`
                  }
                  createSecretLabel="Paste JSON credentials"
                  allowCustomValue={(search) => !looksLikeJson(search)}
                  recommendedKeys={[]}
                  otherKeys={secretKeys}
                  onCreateSecret={(suggestedValue) => {
                    openModal(
                      <WriteSecretModal
                        providerNames={providerNames}
                        initialValue={suggestedValue}
                        multiline={true}
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
          );
        }}
      />
    );
  },
};
