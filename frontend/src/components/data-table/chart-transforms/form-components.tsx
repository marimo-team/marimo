/* Copyright 2024 Marimo. All rights reserved. */

import {
  FormField,
  FormItem,
  FormLabel,
  FormControl,
} from "@/components/ui/form";
import type { UseFormReturn, Path, PathValue } from "react-hook-form";
import type { DataType } from "@/core/kernel/messages";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DATA_TYPE_ICON } from "@/components/datasets/icons";
import { DebouncedInput } from "@/components/ui/input";
import { NONE_GROUP_BY } from "./chart-spec";
import { SquareFunctionIcon } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/utils/cn";

export const ColumnSelector = <T extends object>({
  form,
  name,
  formFieldLabel,
  columns,
  includeNoneOption = false,
}: {
  form: UseFormReturn<T>;
  name: Path<T>;
  formFieldLabel: string;
  columns: Array<{ name: string; type: DataType }>;
  includeNoneOption?: boolean;
}) => {
  return (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormLabel>{formFieldLabel}</FormLabel>
          <FormControl>
            <Select
              {...field}
              onValueChange={(value) => {
                if (value === NONE_GROUP_BY) {
                  form.setValue(name, value as PathValue<T, Path<T>>);
                  return;
                }

                const column = columns.find((column) => column.name === value);
                if (column) {
                  form.setValue(name, value as PathValue<T, Path<T>>);
                  const typeFieldName = name.replace(
                    ".field",
                    ".type",
                  ) as Path<T>;
                  form.setValue(
                    typeFieldName,
                    column.type as PathValue<T, Path<T>>,
                  );
                }
              }}
              value={field.value ?? ""}
            >
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {includeNoneOption && (
                  <SelectItem value={NONE_GROUP_BY}>
                    <div className="flex items-center">
                      <SquareFunctionIcon className="w-3 h-3 mr-2" />
                      None
                    </div>
                  </SelectItem>
                )}
                {columns.map((column) => {
                  const DataTypeIcon = DATA_TYPE_ICON[column.type];
                  return (
                    <SelectItem key={column.name} value={column.name}>
                      <div className="flex items-center">
                        <DataTypeIcon className="w-3 h-3 mr-2" />
                        {column.name}
                      </div>
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
          </FormControl>
        </FormItem>
      )}
    />
  );
};

export const InputField = <T extends object>({
  form,
  name,
  formFieldLabel,
}: {
  form: UseFormReturn<T>;
  name: Path<T>;
  formFieldLabel: string;
}) => {
  return (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormLabel>{formFieldLabel}</FormLabel>
          <FormControl>
            <DebouncedInput
              {...field}
              value={field.value ?? ""}
              onValueChange={field.onChange}
            />
          </FormControl>
        </FormItem>
      )}
    />
  );
};

export const BooleanField = <T extends object>({
  form,
  name,
  formFieldLabel,
  className,
}: {
  form: UseFormReturn<T>;
  name: Path<T>;
  formFieldLabel: string;
  className?: string;
}) => {
  return (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem className={cn("flex flex-row items-center gap-2", className)}>
          <FormLabel>{formFieldLabel}</FormLabel>
          <FormControl>
            <Checkbox
              checked={field.value}
              onCheckedChange={field.onChange}
              className="w-4 h-4"
            />
          </FormControl>
        </FormItem>
      )}
    />
  );
};
