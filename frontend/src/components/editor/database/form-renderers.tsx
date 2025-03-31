/* Copyright 2024 Marimo. All rights reserved. */

import type { FormRenderer } from "@/components/forms/form";
import { FieldOptions } from "@/components/forms/options";
import {
  FormField,
  FormItem,
  FormLabel,
  FormDescription,
  FormControl,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { SECRETS_REGISTRY } from "@/core/secrets/request-registry";
import { KeyIcon } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";
import { z } from "zod";
import { useAsyncData } from "@/hooks/useAsyncData";

import { createContext, useContext, type ReactNode } from "react";
import { Functions } from "@/utils/functions";
import { NumberField } from "@/components/ui/number-field";
import { displaySecret, isSecret, prefixSecret } from "./secrets";

interface SecretsContextType {
  secretKeys: string[];
  loading: boolean;
  error: Error | undefined;
  refreshSecrets: () => void;
}

const SecretsContext = createContext<SecretsContextType>({
  secretKeys: [],
  loading: false,
  error: undefined,
  refreshSecrets: Functions.NOOP,
});

export const useSecrets = () => useContext(SecretsContext);

interface SecretsProviderProps {
  children: ReactNode;
}

export const SecretsProvider = ({ children }: SecretsProviderProps) => {
  const {
    data: secretKeys = [],
    loading,
    error,
    reload,
  } = useAsyncData(async () => {
    const result = await SECRETS_REGISTRY.request({});
    return result?.secrets?.[0]?.keys || [];
  }, []);

  return (
    <SecretsContext.Provider
      value={{ secretKeys, loading, error, refreshSecrets: reload }}
    >
      {children}
    </SecretsContext.Provider>
  );
};

export const ENV_RENDERER: FormRenderer<z.ZodString | z.ZodNumber> = {
  isMatch: (schema: z.ZodType): schema is z.ZodString | z.ZodNumber => {
    // string or number with optionsRegex
    if (schema instanceof z.ZodString || schema instanceof z.ZodNumber) {
      const { optionRegex } = FieldOptions.parse(schema._def.description || "");
      return Boolean(optionRegex);
    }

    return false;
  },
  Component: ({ schema, form, path }) => {
    const { secretKeys } = useSecrets();

    const {
      label,
      description,
      optionRegex = "",
    } = FieldOptions.parse(schema._def.description || "");

    const filteredSecretKeys = secretKeys.filter((key) =>
      new RegExp(optionRegex, "i").test(key),
    );

    return (
      <FormField
        control={form.control}
        name={path}
        render={({ field }) => (
          <FormItem>
            <FormLabel>{label}</FormLabel>
            <FormDescription>{description}</FormDescription>
            <FormControl>
              <div className="flex gap-2">
                {schema instanceof z.ZodString ? (
                  <Input
                    {...field}
                    value={displaySecret(field.value as string)}
                    onChange={field.onChange}
                    className={cn("flex-1")}
                  />
                ) : (
                  <NumberField
                    {...field}
                    value={field.value as number}
                    onChange={field.onChange}
                    className="flex-1"
                  />
                )}
                {filteredSecretKeys.length > 0 && (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild={true}>
                      <Button
                        variant="outline"
                        size="icon"
                        className={cn(
                          isSecret(field.value as string) && "bg-accent",
                        )}
                      >
                        <KeyIcon className="h-3 w-3" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent
                      align="end"
                      className="max-h-60 overflow-y-auto"
                    >
                      {filteredSecretKeys.map((key) => (
                        <DropdownMenuItem
                          key={key}
                          onSelect={() => field.onChange(prefixSecret(key))}
                        >
                          {displaySecret(key)}
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                )}
              </div>
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />
    );
  },
};
