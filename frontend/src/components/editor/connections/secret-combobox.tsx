/* Copyright 2026 Marimo. All rights reserved. */

import { ChevronDownIcon, KeyIcon, PlusCircleIcon, XIcon } from "lucide-react";
import React, { useState } from "react";
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
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  const trimmedSearch = search.trim();
  // Non-secret fields may commit a literal even when it collides with an
  // existing secret key, so we intentionally don't filter out matches here.
  const showCustomValue =
    !secretsOnly && trimmedSearch.length > 0 && trimmedSearch !== value;

  const displayValue = (() => {
    if (!value) {
      return null;
    }
    if (isSecret(value)) {
      return displaySecret(value);
    }
    return value;
  })();

  const selectSecret = (key: string) => {
    onChange(prefixSecret(key));
    setOpen(false);
    setSearch("");
  };

  const selectCustom = (custom: string) => {
    onChange(custom);
    setOpen(false);
    setSearch("");
  };

  const clearValue = () => {
    onChange("");
    setSearch("");
  };

  return (
    <Popover
      modal={true} // own scroll lock so trackpad/wheel works inside the portaled list
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          setSearch("");
        }
      }}
    >
      <PopoverTrigger asChild={true}>
        <button
          type="button"
          className={cn(
            "flex h-6 w-full mb-1 shadow-xs-solid items-center justify-between",
            "rounded-sm border border-input bg-background px-1.5 text-sm font-code ring-offset-background placeholder:text-muted-foreground",
            "hover:shadow-sm-solid focus:outline-hidden focus:ring-1 focus:ring-ring focus:border-primary focus:shadow-md-solid",
            "min-w-48",
            isSecret(value) && "bg-accent",
            className,
          )}
          aria-expanded={open}
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
          {value && (
            <span
              aria-label="Clear"
              className="ml-1 shrink-0 rounded-sm p-0.5 hover:bg-muted cursor-pointer"
              onPointerDown={(e) => {
                e.preventDefault();
                e.stopPropagation();
                clearValue();
              }}
            >
              <XIcon className="h-3.5 w-3.5 opacity-50 hover:opacity-90" />
            </span>
          )}
          <ChevronDownIcon className="ml-1 h-4 w-4 opacity-50 shrink-0" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        className="w-(--radix-popover-trigger-width) p-0"
        align="start"
      >
        <Command>
          <CommandInput
            placeholder={
              secretsOnly
                ? "Search secrets..."
                : "Type a value or search secrets..."
            }
            rootClassName="px-1 h-8"
            autoFocus={true}
            value={search}
            onValueChange={setSearch}
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
                // Include search so this stays visible while filtering
                value={`create new secret ${trimmedSearch}`}
                onSelect={() => {
                  const suggestedValue = trimmedSearch || undefined;
                  setOpen(false);
                  setSearch("");
                  onCreateSecret(suggestedValue);
                }}
              >
                <PlusCircleIcon className="mr-2 h-3.5 w-3.5" />
                Create a new secret
              </CommandItem>
            </CommandGroup>
            {recommendedKeys.length > 0 && (
              <>
                <CommandSeparator className="mt-0" />
                <CommandGroup heading="Recommended">
                  {recommendedKeys.map((key) => (
                    <CommandItem
                      key={key}
                      value={key}
                      onSelect={() => selectSecret(key)}
                    >
                      <KeyIcon className="mr-2 h-3 w-3 opacity-70" />
                      {key}
                    </CommandItem>
                  ))}
                </CommandGroup>
              </>
            )}
            {otherKeys.length > 0 && (
              <>
                <CommandSeparator className="mt-0" />
                <CommandGroup
                  heading={recommendedKeys.length > 0 ? "Other" : undefined}
                >
                  {otherKeys.map((key) => (
                    <CommandItem
                      key={key}
                      value={key}
                      onSelect={() => selectSecret(key)}
                    >
                      <KeyIcon className="mr-2 h-3 w-3 opacity-70" />
                      {key}
                    </CommandItem>
                  ))}
                </CommandGroup>
              </>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
};
