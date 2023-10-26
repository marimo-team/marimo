/* Copyright 2023 Marimo. All rights reserved. */
import { ChevronDownIcon, Check } from "lucide-react";
import { createContext, useContext } from "react";
import { cn } from "../../lib/utils";
import { useControllableState } from "@radix-ui/react-use-controllable-state";
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "./command";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";
import { Functions } from "../../utils/functions";

interface ComboboxContextValue {
  isSelected: (value: unknown) => boolean;
  onSelect: (value: unknown) => void;
}

export const ComboboxContext = createContext<ComboboxContextValue>({
  isSelected: () => false,
  onSelect: Functions.NOOP,
});

interface ComboboxCommonProps<TValue> {
  children: React.ReactNode;
  displayValue?: (item: TValue) => string;
  placeholder?: string;
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  inputPlaceholder?: string;
  search?: string;
  onSearchChange?: (search: string) => void;
  emptyState?: React.ReactNode;
  className?: string;
}

type ComboboxFilterProps =
  | {
      shouldFilter?: true;
      filterFn?: React.ComponentProps<typeof Command>["filter"];
    }
  | {
      shouldFilter: false;
      filterFn?: never;
    };

type ComboboxValueProps<TValue> =
  | {
      multiple?: false;
      value?: TValue | null;
      defaultValue?: TValue | null;
      onValueChange?(value: TValue | null): void;
    }
  | {
      multiple: true;
      value?: TValue[] | null;
      defaultValue?: TValue[] | null;
      onValueChange?(value: TValue[] | null): void;
    };

export type ComboboxProps<TValue> = ComboboxCommonProps<TValue> &
  ComboboxValueProps<TValue> &
  ComboboxFilterProps;

export const Combobox = <TValue,>({
  children,
  displayValue,
  className,
  placeholder = "--",
  value: valueProp,
  defaultValue,
  onValueChange,
  multiple = false,
  shouldFilter = true,
  filterFn,
  open: openProp,
  defaultOpen,
  onOpenChange,
  inputPlaceholder = "Search...",
  search,
  onSearchChange,
  emptyState = "Nothing found.",
}: ComboboxProps<TValue>) => {
  const [open = false, setOpen] = useControllableState({
    prop: openProp,
    defaultProp: defaultOpen,
    onChange: onOpenChange,
  });
  const [value, setValue] = useControllableState({
    prop: valueProp,
    defaultProp: defaultValue,
    onChange: (state) => {
      onValueChange?.(state as unknown as TValue & TValue[]);
    },
  });

  const isSelected = (selectedValue: unknown) => {
    if (Array.isArray(value)) {
      return value.includes(selectedValue as TValue);
    }
    return value === selectedValue;
  };

  const handleSelect = (selectedValue: unknown) => {
    let newValue: TValue | TValue[] | null = selectedValue as TValue;

    if (multiple) {
      if (Array.isArray(value)) {
        if (value.includes(newValue)) {
          const newArr = value.filter((val) => val !== selectedValue);
          newValue = newArr.length > 0 ? newArr : null;
        } else {
          newValue = [...value, newValue];
        }
      } else {
        newValue = [newValue];
      }
    } else if (value === selectedValue) {
      newValue = null;
    }

    setValue(newValue);
    setOpen(false);
  };

  const renderValue = (): string => {
    if (value) {
      if (Array.isArray(value)) {
        if (value.length === 0) {
          return placeholder;
        }
        if (value.length === 1 && displayValue !== undefined) {
          return displayValue(value[0]);
        }
        return `${value.length} selected`;
      }
      if (displayValue !== undefined) {
        return displayValue(value as unknown as TValue);
      }
      return placeholder;
    }
    return placeholder;
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild={true}>
        <div
          className={cn(
            "flex h-6 w-fit mb-1 shadow-xsSolid items-center justify-between rounded-sm border border-input bg-transparent px-2 text-sm font-prose ring-offset-background placeholder:text-muted-foreground hover:shadow-smSolid focus:outline-none focus:ring-1 focus:ring-ring focus:border-primary focus:shadow-mdSolid disabled:cursor-not-allowed disabled:opacity-50",
            className
          )}
          aria-expanded={open}
        >
          {renderValue()} <ChevronDownIcon className="ml-3 w-4 h-4" />
        </div>
      </PopoverTrigger>
      <PopoverContent
        className="w-full min-w-[var(--radix-popover-trigger-width)] p-0"
        align="start"
      >
        <Command filter={filterFn} shouldFilter={shouldFilter}>
          <CommandInput
            placeholder={inputPlaceholder}
            rootClassName={"px-2 h-10"}
            autoFocus={true}
            value={search}
            onValueChange={onSearchChange}
          />
          <CommandList className="max-h-60 py-.5">
            <CommandEmpty>{emptyState}</CommandEmpty>
            <ComboboxContext.Provider
              value={{ isSelected, onSelect: handleSelect }}
            >
              {children}
            </ComboboxContext.Provider>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
};

interface ComboboxItemOptions<TValue> {
  value: TValue;
}

export interface ComboboxItemProps<TValue>
  extends ComboboxItemOptions<TValue>,
    Omit<
      React.ComponentProps<typeof CommandItem>,
      keyof ComboboxItemOptions<TValue> | "onSelect" | "role"
    > {
  onSelect?(value: TValue): void;
}

export const ComboboxItem = <
  TValue = Parameters<typeof Combobox>[0]["value"],
>({
  children,
  className,
  value,
  onSelect,
}: ComboboxItemProps<TValue>) => {
  const context = useContext(ComboboxContext);

  return (
    <CommandItem
      className={cn("pl-6 m-1 py-1", className)}
      role="option"
      onSelect={() => {
        context.onSelect(value);
        onSelect?.(value);
      }}
    >
      {context.isSelected(value) && (
        <Check className="absolute left-1 h-4 w-4" />
      )}
      {children}
    </CommandItem>
  );
};
