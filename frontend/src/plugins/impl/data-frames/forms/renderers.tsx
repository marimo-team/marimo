/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */

import React, { useEffect } from "react";
import {
  type FieldValues,
  type Path,
  type UseFormReturn,
  useWatch,
} from "react-hook-form";
import { z } from "zod";
import { type FormRenderer, renderZodSchema } from "@/components/forms/form";
import { FieldOptions } from "@/components/forms/options";
import {
  ensureStringArray,
  SwitchableMultiSelect,
  TextAreaMultiSelect,
} from "@/components/forms/switchable-multi-select";
import { Combobox, ComboboxItem } from "@/components/ui/combobox";
import {
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  FormMessageTooltip,
} from "@/components/ui/form";
import { DebouncedInput } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAsyncData } from "@/hooks/useAsyncData";
import { cn } from "@/utils/cn";
import { Objects } from "@/utils/objects";
import { Strings } from "@/utils/strings";
import type { ColumnId } from "../types";
import { getOperatorForDtype, getSchemaForOperator } from "../utils/operators";
import {
  ColumnFetchValuesContext,
  ColumnInfoContext,
  ColumnNameContext,
} from "./context";
import { DataTypeIcon } from "./datatype-icon";

export const columnIdRenderer = <T extends FieldValues>(): FormRenderer<
  T,
  string
> => ({
  isMatch: (schema: z.ZodType): schema is z.ZodString => {
    const { special } = FieldOptions.parse(schema._def.description || "");
    return special === "column_id";
  },
  Component: ({ schema, form, path }) => {
    const columns = React.use(ColumnInfoContext);
    const { label, description } = FieldOptions.parse(schema._def.description);

    return (
      <FormField
        control={form.control}
        name={path}
        render={({ field }) => (
          <FormItem>
            <FormLabel>{label}</FormLabel>
            <FormDescription>{description}</FormDescription>
            <FormControl>
              <Select
                data-testid="marimo-plugin-data-frames-column-select"
                value={
                  field.value == null
                    ? field.value
                    : JSON.stringify(field.value)
                }
                onValueChange={(value) => {
                  const realValue = JSON.parse(value);
                  field.onChange(realValue);
                }}
              >
                <div className="flex items-center gap-1">
                  <SelectTrigger className="min-w-[180px]">
                    <SelectValue placeholder="--" />
                  </SelectTrigger>
                  <StyledFormMessage />
                </div>

                <SelectContent>
                  <SelectGroup>
                    {[...columns.entries()].map(([name, dtype]) => (
                      <SelectItem key={name} value={JSON.stringify(name)}>
                        <span className="flex items-center gap-2 flex-1">
                          <DataTypeIcon type={dtype} />
                          <span className="flex-1">{name}</span>
                          <span className="text-muted-foreground text-xs font-semibold">
                            ({dtype})
                          </span>
                        </span>
                      </SelectItem>
                    ))}
                    {columns.size === 0 && (
                      <SelectItem disabled={true} value="--">
                        No columns
                      </SelectItem>
                    )}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </FormControl>
          </FormItem>
        )}
      />
    );
  },
});

export const multiColumnIdRenderer = <T extends FieldValues>(): FormRenderer<
  T,
  string[]
> => ({
  isMatch: (schema: z.ZodType): schema is z.ZodArray<z.ZodString> => {
    if (schema instanceof z.ZodArray) {
      const childType = schema._def.type;
      const { special } = FieldOptions.parse(childType._def.description || "");
      return special === "column_id";
    }
    return false;
  },
  Component: ({ schema, form, path }) => {
    const { label } = FieldOptions.parse(schema._def.description);
    return (
      <MultiColumnFormField
        schema={schema}
        form={form}
        path={path}
        itemLabel={label}
      />
    );
  },
});

/**
 * Type: (string | number)[]
 * Special: column_ids
 */
const MultiColumnFormField = ({
  schema,
  form,
  path,
  itemLabel,
}: {
  schema: z.ZodSchema;
  form: UseFormReturn<any>;
  path: Path<any>;
  itemLabel?: string;
}) => {
  const columns = React.use(ColumnInfoContext);
  const { description } = FieldOptions.parse(schema._def.description);
  const placeholder = itemLabel
    ? `Select ${itemLabel.toLowerCase()}`
    : undefined;
  return (
    <FormField
      control={form.control}
      name={path}
      render={({ field }) => {
        const values = ensureStringArray(field.value);
        return (
          <FormItem>
            <FormLabel>{itemLabel}</FormLabel>
            <FormDescription>{description}</FormDescription>
            <FormControl>
              <Combobox<ColumnId>
                className="min-w-[180px]"
                placeholder={placeholder}
                displayValue={String}
                multiple={true}
                chips={true}
                keepPopoverOpenOnSelect={true}
                value={values}
                onValueChange={(v) => {
                  field.onChange(v);
                }}
              >
                {[...columns.entries()].map(([name, dtype]) => {
                  return (
                    <ComboboxItem key={name} value={name}>
                      <span className="flex items-center gap-2 flex-1">
                        <DataTypeIcon type={dtype} />
                        <span className="flex-1">{name}</span>
                        <span className="text-muted-foreground text-xs font-semibold">
                          ({dtype})
                        </span>
                      </span>
                    </ComboboxItem>
                  );
                })}
              </Combobox>
            </FormControl>
            <FormMessage />
          </FormItem>
        );
      }}
    />
  );
};

export const columnValuesRenderer = <T extends FieldValues>(): FormRenderer<
  T,
  string[]
> => ({
  isMatch: (schema: z.ZodType): schema is z.ZodArray<z.ZodString> => {
    if (schema instanceof z.ZodArray) {
      const { special } = FieldOptions.parse(schema._def.description || "");
      return special === "column_values";
    }
    return false;
  },
  Component: ({ schema, form, path }) => {
    const { label, description, placeholder } = FieldOptions.parse(
      schema._def.description,
    );
    const column = React.use(ColumnNameContext);
    const fetchValues = React.use(ColumnFetchValuesContext);
    const { data, isPending } = useAsyncData(
      () => fetchValues({ column }),
      [column],
    );

    const options = data?.values || [];

    if (options.length === 0 && !isPending) {
      return (
        <FormField
          control={form.control}
          name={path}
          render={({ field }) => (
            <FormItem>
              <FormLabel>{label}</FormLabel>
              <FormDescription>{description}</FormDescription>
              <FormControl>
                <DebouncedInput
                  {...field}
                  value={field.value}
                  onValueChange={field.onChange}
                  className="my-0"
                  placeholder={placeholder}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
      );
    }

    const optionsAsStrings = options.map(String);
    return (
      <FormField
        control={form.control}
        name={path}
        render={({ field }) => (
          <FormItem>
            <FormLabel className="whitespace-pre">{label}</FormLabel>
            <FormDescription>{description}</FormDescription>
            <FormControl>
              <Combobox
                className="min-w-[180px]"
                placeholder={placeholder}
                multiple={false}
                displayValue={(option: string) => option}
                value={
                  Array.isArray(field.value) ? field.value[0] : field.value
                }
                onValueChange={field.onChange}
              >
                {optionsAsStrings.map((option) => (
                  <ComboboxItem key={option} value={option}>
                    {option}
                  </ComboboxItem>
                ))}
              </Combobox>
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />
    );
  },
});

export const multiColumnValuesRenderer = <
  T extends FieldValues,
>(): FormRenderer<T> => ({
  isMatch: (schema: z.ZodType): schema is z.ZodArray<z.ZodString> => {
    const { special } = FieldOptions.parse(schema._def.description || "");
    return special === "column_values" && schema instanceof z.ZodArray;
  },
  Component: ({ schema, form, path }) => {
    const column = React.use(ColumnNameContext);
    const fetchValues = React.use(ColumnFetchValuesContext);
    const { data, isPending } = useAsyncData(
      () => fetchValues({ column }),
      [column],
    );

    const options = data?.values || [];

    if (options.length === 0 && !isPending) {
      return (
        <FormField
          control={form.control}
          name={path}
          render={({ field }) => (
            <FormItem>
              <FormLabel>{schema.description}</FormLabel>
              <FormControl>
                <TextAreaMultiSelect {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
      );
    }

    const optionsAsStrings = options.map(String);
    return (
      <FormField
        control={form.control}
        name={path}
        render={({ field }) => {
          const valueAsArray = ensureStringArray(field.value);
          return (
            <FormItem>
              <FormLabel>{schema.description}</FormLabel>
              <FormControl>
                <SwitchableMultiSelect
                  {...field}
                  value={valueAsArray}
                  options={optionsAsStrings}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          );
        }}
      />
    );
  },
});

const StyledFormMessage = ({ className }: { className?: string }) => {
  return (
    <FormMessageTooltip
      className={cn("text-destructive text-xs w-[16px]", className)}
    />
  );
};

export const filterFormRenderer = <T extends FieldValues>(): FormRenderer<
  T,
  {}
> => ({
  isMatch: (schema: z.ZodType): schema is z.ZodObject<{}> => {
    if (schema instanceof z.ZodObject) {
      const { special } = FieldOptions.parse(schema._def.description || "");
      return special === "column_filter";
    }
    return false;
  },
  Component: ({ schema, form, path }) => {
    return (
      <ColumnFilterForm
        schema={schema as z.ZodObject<{}>}
        form={form}
        path={path}
      />
    );
  },
});

const ColumnFilterForm = <T extends FieldValues>({
  path,
  form,
  schema,
}: {
  schema: z.ZodObject<{}>;
  form: UseFormReturn<any>;
  path: Path<any>;
}) => {
  const { description } = FieldOptions.parse(schema._def.description);
  const columns = React.use(ColumnInfoContext);

  const columnIdSchema = Objects.entries(schema._def.shape()).find(
    ([key]) => key === "column_id",
  )?.[1] as unknown as z.ZodString;

  // existing values
  const { column_id: columnId, operator } = useWatch({
    name: path,
  }) as {
    column_id: ColumnId;
    operator: string;
  };

  const columnRenderer = columnIdRenderer<T>();
  const children = [
    renderZodSchema(columnIdSchema, form, `${path}.column_id` as Path<T>, [
      columnRenderer,
    ]),
  ];

  // When column ID changes, get the new dtype and reset the operator
  useEffect(() => {
    const dtype = columns.get(columnId);
    const operators = getOperatorForDtype(dtype);

    const currentOperator = form.getValues(`${path}.operator`);
    if (!operators.includes(currentOperator)) {
      form.setValue(`${path}.operator`, operators[0]);
      form.setValue(`${path}.value`, undefined);
    }
  }, [columnId, columns, form, path]);

  if (columnId != null) {
    const dtype = columns.get(columnId);
    const operators = getOperatorForDtype(dtype);

    if (operators.length === 0) {
      children.push(
        <div
          key="no_operator"
          className="text-muted-foreground text-xs font-semibold"
        >
          <FormLabel className="whitespace-pre"> </FormLabel>
          <p>This column type does not support filtering.</p>
        </div>,
      );
    } else {
      children.push(
        <FormField
          key="operator"
          control={form.control}
          name={`${path}.operator` as Path<T>}
          render={({ field }) => (
            <FormItem>
              <FormLabel className="whitespace-pre"> </FormLabel>
              <FormDescription>{description}</FormDescription>
              <FormControl>
                <Select
                  data-testid="marimo-plugin-data-frames-filter-operator-select"
                  value={field.value}
                  onValueChange={field.onChange}
                >
                  <SelectTrigger className="min-w-[140px]">
                    <SelectValue placeholder="--" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {operators.map((value: string) => (
                        <SelectItem key={value} value={value}>
                          {Strings.startCase(value)}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />,
      );
    }
  }

  if (operator != null) {
    const dtype = columns.get(columnId);
    const operandSchemas = getSchemaForOperator(dtype, operator);
    if (operandSchemas.length === 1) {
      children.push(
        <React.Fragment key="value">
          {renderZodSchema(
            operandSchemas[0],
            form,
            `${path}.value` as Path<T>,
            [],
          )}
        </React.Fragment>,
      );
    }
  }

  return (
    <FormField
      control={form.control}
      name={path}
      render={() => (
        <div className="flex flex-col gap-2">
          <div className={cn("flex flex-row gap-2")}>{children}</div>
          <FormMessage />
        </div>
      )}
    />
  );
};

export const DATAFRAME_FORM_RENDERERS: FormRenderer[] = [
  columnIdRenderer(),
  multiColumnIdRenderer(),
  columnValuesRenderer(),
  multiColumnValuesRenderer(),
  filterFormRenderer(),
];
