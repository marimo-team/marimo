/* Copyright 2024 Marimo. All rights reserved. */

import {
  FormField,
  FormItem,
  FormLabel,
  FormControl,
} from "@/components/ui/form";
import type { UseFormReturn } from "react-hook-form";
import type { ChartSchema } from "./chart-schemas";
import type { DataType } from "@/core/kernel/messages";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DATA_TYPE_ICON } from "@/components/datasets/icons";
import type { z } from "zod";
import { DebouncedInput } from "@/components/ui/input";

export const ColumnSelector = ({
  form,
  formFieldName,
  formFieldLabel,
  columns,
}: {
  form: UseFormReturn<z.infer<typeof ChartSchema>>;
  formFieldName: "general.xColumn.field" | "general.yColumn.field";
  formFieldLabel: string;
  columns: Array<{ name: string; type: DataType }>;
}) => {
  return (
    <FormField
      control={form.control}
      name={formFieldName}
      render={({ field }) => (
        <FormItem>
          <FormLabel>{formFieldLabel}</FormLabel>
          <FormControl>
            <Select
              {...field}
              onValueChange={(value) => {
                const column = columns.find((column) => column.name === value);
                if (column) {
                  form.setValue(formFieldName, value);
                  const typeFieldName = formFieldName.replace(
                    ".field",
                    ".type",
                  ) as "general.xColumn.type" | "general.yColumn.type";
                  form.setValue(typeFieldName, column.type);
                }
              }}
              value={field.value ?? ""}
            >
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
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

export const AxisLabelForm = ({
  form,
  formFieldName,
  formFieldLabel,
}: {
  form: UseFormReturn<z.infer<typeof ChartSchema>>;
  formFieldName: "xAxis.label" | "yAxis.label";
  formFieldLabel: string;
}) => {
  return (
    <FormField
      control={form.control}
      name={formFieldName}
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
