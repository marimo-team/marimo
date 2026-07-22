/* Copyright 2026 Marimo. All rights reserved. */

import { ChevronDownIcon, KeyIcon, PlusCircleIcon, XIcon } from "lucide-react";
import React, { useMemo } from "react";
import {
  Command,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { type Option, useSelectList } from "@/components/ui/select-core";
import { cn } from "@/utils/cn";
import { displaySecret, isSecret, prefixSecret } from "./secrets";

export function partitionSecretKeys(
  secretKeys: string[],
  optionRegex: string,
): { recommended: string[]; other: string[] } {
  if (!optionRegex) {
    return { recommended: [], other: [...secretKeys] };
  }

  let pattern: RegExp;
  try {
    pattern = new RegExp(optionRegex, "i");
  } catch {
    return { recommended: [], other: [...secretKeys] };
  }

  const recommended: string[] = [];
  const other: string[] = [];
  for (const key of secretKeys) {
    if (pattern.test(key)) {
      recommended.push(key);
    } else {
      other.push(key);
    }
  }
  return { recommended, other };
}

type SecretSection = "recommended" | "other";

interface SecretComboboxProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  /** When true, only secrets (or creating one) can be chosen — no free-text literals. */
  secretsOnly?: boolean;
  recommendedKeys: string[];
  otherKeys: string[];
  /** Opens the create-secret flow; `suggestedValue` is the current search text when present. */
  onCreateSecret: (suggestedValue?: string) => void;
  className?: string;
}

/**
 * Searchable combobox for connection fields that may reference secrets.
 *
 * - Default: pick a secret, create one, or commit a free-text literal.
 * - `secretsOnly`: pick or create a secret only (for passwords/tokens/keys).
 */
export const SecretCombobox: React.FC<SecretComboboxProps> = ({
  value,
  onChange,
  placeholder,
  secretsOnly = false,
  recommendedKeys,
  otherKeys,
  onCreateSecret,
  className,
}) => {
  const options = useMemo<Array<Option<string>>>(
    () => [
      ...recommendedKeys.map((key) => ({
        value: key,
        label: key,
        data: { section: "recommended" as const satisfies SecretSection },
      })),
      ...otherKeys.map((key) => ({
        value: key,
        label: key,
        data: { section: "other" as const satisfies SecretSection },
      })),
    ],
    [recommendedKeys, otherKeys],
  );

  // Field value is `secret("KEY")` or a literal; the list selects bare keys.
  const selectedKey = isSecret(value) ? displaySecret(value) : null;

  const list = useSelectList({
    options,
    value: selectedKey,
    onChange: (next) => {
      onChange(next == null ? "" : prefixSecret(next));
    },
    multiple: false,
  });

  const trimmedSearch = list.searchQuery.trim();
  // Non-secret fields may commit a literal even when it collides with an
  // existing secret key, so we intentionally don't filter out matches here.
  const showCustomValue =
    !secretsOnly && trimmedSearch.length > 0 && trimmedSearch !== value;

  const sectionOf = (option: Option<string>): SecretSection =>
    (option.data as { section: SecretSection }).section;
  const recommendedVisible = list.visibleOptions.filter(
    (option) => sectionOf(option) === "recommended",
  );
  const otherVisible = list.visibleOptions.filter(
    (option) => sectionOf(option) === "other",
  );

  const displayValue = (() => {
    if (!value) {
      return null;
    }
    if (isSecret(value)) {
      return displaySecret(value);
    }
    return value;
  })();

  const selectCustom = (custom: string) => {
    onChange(custom);
    list.setOpen(false);
  };

  const clearValue = () => {
    onChange("");
    list.setOpen(false);
  };

  return (
    <div
      className={cn("flex w-full min-w-48 mb-1 items-center gap-1", className)}
    >
      <Popover
        modal={true} // own scroll lock so trackpad/wheel works inside the portaled list
        open={list.open}
        onOpenChange={list.setOpen}
      >
        <PopoverTrigger asChild={true}>
          <button
            type="button"
            className={cn(
              "flex h-6 min-w-0 flex-1 shadow-xs-solid items-center justify-between",
              "rounded-sm border border-input bg-background px-1.5 text-sm font-code ring-offset-background placeholder:text-muted-foreground",
              "hover:shadow-sm-solid focus:outline-hidden focus:ring-1 focus:ring-ring focus:border-primary focus:shadow-md-solid",
              isSecret(value) && "bg-accent",
            )}
            aria-expanded={list.open}
          >
            <span className="truncate flex-1 min-w-0 text-left flex items-center gap-1.5">
              {displayValue ? (
                <>
                  {isSecret(value) && (
                    <KeyIcon className="h-3 w-3 shrink-0 opacity-70" />
                  )}
                  <span className="truncate">{displayValue}</span>
                </>
              ) : (
                <span className="text-muted-foreground">{placeholder}</span>
              )}
            </span>
            <ChevronDownIcon className="ml-1 h-4 w-4 opacity-50 shrink-0" />
          </button>
        </PopoverTrigger>
        <PopoverContent
          className="w-(--radix-popover-trigger-width) p-0"
          align="start"
        >
          <Command shouldFilter={false}>
            <CommandInput
              placeholder={
                secretsOnly
                  ? "Search secrets..."
                  : "Type a value or search secrets..."
              }
              rootClassName="px-1 h-8"
              autoFocus={true}
              value={list.searchQuery}
              onValueChange={list.setSearchQuery}
            />
            <CommandList className="max-h-60 overscroll-contain">
              {showCustomValue && (
                <CommandGroup>
                  <CommandItem
                    value={`use custom value ${trimmedSearch}`}
                    onSelect={() => selectCustom(trimmedSearch)}
                  >
                    Use "{trimmedSearch}"
                  </CommandItem>
                </CommandGroup>
              )}
              {showCustomValue && <CommandSeparator />}
              <CommandGroup className="mt-0">
                <CommandItem
                  value="create new secret"
                  onSelect={() => {
                    const suggestedValue = trimmedSearch || undefined;
                    list.setOpen(false);
                    onCreateSecret(suggestedValue);
                  }}
                >
                  <PlusCircleIcon className="mr-2 h-3.5 w-3.5" />
                  Create a new secret
                </CommandItem>
              </CommandGroup>
              {recommendedVisible.length > 0 && (
                <>
                  <CommandSeparator className="mt-0" />
                  <CommandGroup heading="Recommended">
                    {recommendedVisible.map((option) => (
                      <CommandItem
                        key={option.value}
                        value={option.value}
                        onSelect={() => list.toggle(option.value)}
                      >
                        <KeyIcon className="mr-2 h-3 w-3 opacity-70" />
                        {option.label}
                      </CommandItem>
                    ))}
                  </CommandGroup>
                </>
              )}
              {otherVisible.length > 0 && (
                <>
                  <CommandSeparator className="mt-0" />
                  <CommandGroup
                    heading={
                      recommendedVisible.length > 0 ? "Other" : undefined
                    }
                  >
                    {otherVisible.map((option) => (
                      <CommandItem
                        key={option.value}
                        value={option.value}
                        onSelect={() => list.toggle(option.value)}
                      >
                        <KeyIcon className="mr-2 h-3 w-3 opacity-70" />
                        {option.label}
                      </CommandItem>
                    ))}
                  </CommandGroup>
                </>
              )}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
      {value && (
        <button
          type="button"
          aria-label="Clear"
          className={cn(
            "flex h-6 w-6 shrink-0 items-center justify-center rounded-sm",
            "text-muted-foreground hover:bg-muted hover:text-foreground",
            "focus:outline-hidden focus:ring-1 focus:ring-ring",
          )}
          onClick={clearValue}
        >
          <XIcon className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
};
