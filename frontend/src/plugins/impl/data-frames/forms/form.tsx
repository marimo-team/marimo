/* Copyright 2023 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { z } from "zod";
import { Input } from "../../../../components/ui/input";
import { Checkbox } from "../../../../components/ui/checkbox";
import {
  FieldValues,
  FormProvider,
  Path,
  UseFormReturn,
  useController,
  useFieldArray,
} from "react-hook-form";
import {
  FormField,
  FormItem,
  FormLabel,
  FormControl,
  FormMessage,
  FormDescription,
} from "../../../../components/ui/form";
import { Objects } from "../../../../utils/objects";
import { Button } from "../../../../components/ui/button";
import { getDefaults, getUnionLiteral } from "./form-utils";
import { PlusIcon, Trash2Icon } from "lucide-react";
import { FieldOptions } from "@/plugins/impl/data-frames/forms/options";
import { cn } from "@/lib/utils";
import React, { useContext, useEffect } from "react";
import { ColumnContext } from "@/plugins/impl/data-frames/forms/context";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { getOperatorForDtype, getSchemaForOperator } from "../utils/operators";
import { Textarea } from "@/components/ui/textarea";
import { Strings } from "@/utils/strings";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DataTypeIcon } from "./DataTypeIcon";

interface Props<T extends FieldValues> {
  form: UseFormReturn<T>;
  schema: z.ZodType<any>;
  path?: Path<T>;
}

export const ZodForm = <T extends FieldValues>({
  schema,
  form,
  path = "" as Path<T>,
}: Props<T>) => {
  return (
    <FormProvider {...form}>{renderZodSchema(schema, form, path)}</FormProvider>
  );
};

function renderZodSchema<T extends FieldValues, S>(
  schema: z.ZodType<S>,
  form: UseFormReturn<T>,
  path: Path<T>
) {
  const {
    label,
    description,
    placeholder,
    disabled,
    special,
    direction = "column",
  } = FieldOptions.parse(schema._def.description || "");

  if (schema instanceof z.ZodDefault) {
    let inner = schema._def.innerType as z.ZodType<unknown>;
    // pass along the description
    inner =
      !inner.description && schema.description
        ? inner.describe(schema.description)
        : inner;
    return renderZodSchema(inner, form, path);
  }

  if (schema instanceof z.ZodObject) {
    if (special === "column_filter") {
      return <FilterForm schema={schema} form={form} path={path} />;
    }

    return (
      <div
        className={cn(
          "flex",
          direction === "row" ? "flex-row gap-4 items-start" : "flex-col gap-4"
        )}
      >
        <FormLabel>{label}</FormLabel>
        {Objects.entries(schema._def.shape()).map(([key, value]) => {
          const isLiteral = value instanceof z.ZodLiteral;
          const childForm = renderZodSchema(
            value as z.ZodType<unknown>,
            form,
            `${path}.${key}` as Path<T>
          );

          if (isLiteral) {
            return <React.Fragment key={key}>{childForm}</React.Fragment>;
          }

          return (
            <div className="flex flex-row align-start" key={key}>
              {childForm}
            </div>
          );
        })}
      </div>
    );
  } else if (schema instanceof z.ZodString) {
    if (special === "column_id") {
      return <ColumnSelector schema={schema} form={form} path={path} />;
    }

    return (
      <FormField
        control={form.control}
        name={path}
        render={({ field }) => (
          <FormItem>
            <FormLabel>{label}</FormLabel>
            <FormControl>
              <Input {...field} placeholder={placeholder} disabled={disabled} />
            </FormControl>
            <FormDescription>{description}</FormDescription>
            <FormMessage />
          </FormItem>
        )}
      />
    );
  } else if (schema instanceof z.ZodBoolean) {
    return (
      <FormField
        control={form.control}
        name={path}
        render={({ field }) => (
          <FormItem>
            <div className="flex flex-row items-start space-x-2">
              <FormLabel>{label}</FormLabel>
              <FormControl>
                <Checkbox
                  checked={field.value}
                  onCheckedChange={field.onChange}
                />
              </FormControl>
            </div>
            <FormDescription>{description}</FormDescription>
            <FormMessage />
          </FormItem>
        )}
      />
    );
  } else if (schema instanceof z.ZodNumber) {
    return (
      <FormField
        control={form.control}
        name={path}
        render={({ field }) => (
          <FormItem>
            <FormLabel>{label}</FormLabel>
            <FormControl>
              <Input
                type="number"
                value={field.value}
                onChange={(value) => field.onChange(value.target.valueAsNumber)}
              />
            </FormControl>
            <FormDescription>{description}</FormDescription>
            <FormMessage />
          </FormItem>
        )}
      />
    );
  } else if (schema instanceof z.ZodDate) {
    return (
      <FormField
        control={form.control}
        name={path}
        render={({ field }) => (
          <FormItem>
            <FormLabel>{label}</FormLabel>
            <FormControl>
              <Input {...field} type="date" />
            </FormControl>
            <FormDescription>{description}</FormDescription>
            <FormMessage />
          </FormItem>
        )}
      />
    );
  } else if (schema instanceof z.ZodAny) {
    return (
      <FormField
        control={form.control}
        name={path}
        render={({ field }) => (
          <FormItem>
            <FormLabel>{label}</FormLabel>
            <FormControl>
              <Input {...field} />
            </FormControl>
            <FormDescription>{description}</FormDescription>
            <FormMessage />
          </FormItem>
        )}
      />
    );
  } else if (schema instanceof z.ZodEnum) {
    if (special === "radio_group") {
      return (
        <FormField
          control={form.control}
          name={path}
          render={({ field }) => (
            <FormItem>
              <FormLabel>{label}</FormLabel>
              <FormControl>
                <RadioGroup
                  className="flex flex-row gap-2 pt-1 items-center"
                  value={field.value}
                  onValueChange={field.onChange}
                >
                  {schema._def.values.map((value: string) => {
                    return (
                      <div className="flex items-center gap-1" key={value}>
                        <RadioGroupItem
                          key={value}
                          value={value}
                          id={`${path}-${value}`}
                        />
                        <FormLabel
                          className="whitespace-pre"
                          htmlFor={`${path}-${value}`}
                        >
                          {Strings.startCase(value)}
                        </FormLabel>
                      </div>
                    );
                  })}
                </RadioGroup>
              </FormControl>
              <FormDescription>{description}</FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
      );
    }

    return (
      <FormField
        control={form.control}
        name={path}
        render={({ field }) => (
          <FormItem>
            <FormLabel className="whitespace-pre">{label}</FormLabel>
            <FormControl>
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger className="min-w-[210px]">
                  <SelectValue placeholder="--" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {schema._def.values.map((value: string) => {
                      return (
                        <SelectItem key={value} value={value}>
                          {Strings.startCase(value)}
                        </SelectItem>
                      );
                    })}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </FormControl>
            <FormDescription>{description}</FormDescription>
            <FormMessage />
          </FormItem>
        )}
      />
    );
  } else if (schema instanceof z.ZodArray) {
    if (special === "text_area_multiline") {
      // new-line separated
      const delimiter = "\n";
      return (
        <FormField
          control={form.control}
          name={path}
          render={({ field }) => (
            <FormItem>
              <FormLabel>{label}</FormLabel>
              <FormControl>
                <Textarea
                  value={
                    Array.isArray(field.value)
                      ? field.value.join(delimiter)
                      : field.value
                  }
                  onChange={(e) => {
                    if (e.target.value === "") {
                      field.onChange([]);
                      return;
                    }
                    field.onChange(e.target.value.split(delimiter));
                  }}
                  placeholder={placeholder}
                  disabled={disabled}
                />
              </FormControl>
              <FormDescription>{description}</FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
      );
    }

    return (
      <div className="flex flex-col gap-1">
        <Label>{label}</Label>
        <FormArray
          schema={schema._def.type}
          form={form}
          path={path}
          key={path}
        />
      </div>
    );
  } else if (schema instanceof z.ZodUnion) {
    return (
      <FormField
        control={form.control}
        name={path}
        render={({ field }) => {
          const options = schema._def.options as Array<z.ZodType<unknown>>;
          let value: string = field.value;
          const types = options.map((option) => {
            return getUnionLiteral(option)._def.value;
          });

          if (!value) {
            // Default to first
            value = types[0];
          }

          const selectedOption = options.find((option) => {
            return getUnionLiteral(option)._def.value === value;
          });

          return (
            <div className="flex flex-col">
              <FormLabel>{label}</FormLabel>
              <NativeSelect {...field}>
                {types.map((type: string) => {
                  return (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  );
                })}
              </NativeSelect>
              {selectedOption && renderZodSchema(selectedOption, form, path)}
            </div>
          );
        }}
      />
    );
  } else if (schema instanceof z.ZodLiteral) {
    return (
      <FormField
        control={form.control}
        name={path}
        render={({ field }) => <Input {...field} type="hidden" />}
      />
    );
  } else if (
    schema instanceof z.ZodEffects &&
    schema._def.effect.type === "refinement"
  ) {
    return renderZodSchema(schema._def.schema, form, path);
  } else if (schema instanceof z.ZodRecord) {
    return (
      <FormField
        control={form.control}
        name={path}
        render={({ field }) => (
          <FormItem>
            <FormLabel>{label}</FormLabel>
            <FormControl>
              <Input {...field} />
            </FormControl>
            <FormDescription>{description}</FormDescription>
            <FormMessage />
          </FormItem>
        )}
      />
    );
  } else {
    return (
      <div>
        Unknown schema type{" "}
        {schema ? JSON.stringify(schema._type || schema) : path}
      </div>
    );
  }
}

const FormArray = ({
  schema,
  form,
  path,
}: {
  schema: z.ZodType<unknown>;
  form: UseFormReturn<any>;
  path: Path<any>;
}) => {
  const { label, description } = FieldOptions.parse(
    schema._def.description || ""
  );

  const control = form.control;
  // prepend, remove, swap, move, insert, replace
  const { fields, append, remove } = useFieldArray({
    control,
    name: path,
  });

  return (
    <div className="flex flex-col gap-2 pt-2 min-w-[220px]">
      <FormLabel>{label}</FormLabel>
      <FormDescription>{description}</FormDescription>
      {fields.map((field, index) => {
        return (
          <div
            className="flex flex-row pl-2 ml-2 border-l-2 border-disabled hover-actions-parent relative pr-5 pt-1"
            key={field.id}
          >
            {renderZodSchema(schema, form, `${path}[${index}]`)}
            <Trash2Icon
              className="w-4 h-4 mr-1 hover-action text-muted-foreground hover:text-destructive absolute -right-1 top-0 cursor-pointer"
              onClick={() => {
                remove(index);
              }}
            />
          </div>
        );
      })}
      <div>
        <Button
          size="xs"
          variant="text"
          onClick={() => {
            append(getDefaults(schema));
          }}
        >
          <PlusIcon className="w-3.5 h-3.5 mr-1" />
          Add
        </Button>
      </div>
    </div>
  );
};

const ColumnSelector = ({
  schema,
  form,
  path,
}: {
  schema: z.ZodString;
  form: UseFormReturn<any>;
  path: Path<any>;
}) => {
  const columns = useContext(ColumnContext);
  const { label, description } = FieldOptions.parse(schema._def.description);

  return (
    <FormField
      control={form.control}
      name={path}
      render={({ field }) => (
        <FormItem>
          <FormLabel>{label}</FormLabel>
          <FormControl>
            <Select value={field.value} onValueChange={field.onChange}>
              <SelectTrigger className="min-w-[210px]">
                <SelectValue placeholder="--" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {Objects.entries(columns).map(([name, dtype]) => {
                    return (
                      <SelectItem key={name} value={name.toString()}>
                        <span className="flex items-center gap-2 flex-1">
                          <DataTypeIcon type={dtype} />
                          <span className="flex-1">{name}</span>
                          <span className="text-muted-foreground text-xs font-semibold">
                            ({dtype})
                          </span>
                        </span>
                      </SelectItem>
                    );
                  })}
                </SelectGroup>
              </SelectContent>
            </Select>
          </FormControl>
          <FormDescription>{description}</FormDescription>
          <FormMessage />
        </FormItem>
      )}
    />
  );
};

const FilterForm = ({
  path,
  form,
  schema,
}: {
  schema: z.ZodObject<{}>;
  form: UseFormReturn<any>;
  path: Path<any>;
}) => {
  const { description } = FieldOptions.parse(schema._def.description);
  const columns = useContext(ColumnContext);
  const { field } = useController({ name: path });

  const columnIdSchema = Objects.entries(schema._def.shape()).find(
    ([key, value]) => {
      return key === "column_id";
    }
  )?.[1] as unknown as z.ZodString;

  // existing values
  const { column_id: columnId, operator } = field.value || {};

  const children = [
    <ColumnSelector
      key={`column_id`}
      schema={columnIdSchema}
      form={form}
      path={`${path}.column_id`}
    />,
  ];

  // When column ID changes, get the new dtype and reset the operator
  useEffect(() => {
    const dtype = columns[columnId];
    const operators = getOperatorForDtype(dtype);

    const currentOperator = form.getValues(`${path}.operator`);
    if (!operators.includes(currentOperator)) {
      form.setValue(`${path}.operator`, operators[0]);
      form.setValue(`${path}.value`, undefined);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [columnId]);

  if (columnId) {
    const dtype = columns[columnId];
    const operators = getOperatorForDtype(dtype);

    if (operators.length === 0) {
      children.push(
        <div
          key={`no_operator`}
          className="text-muted-foreground text-xs font-semibold"
        >
          <FormLabel className="whitespace-pre"> </FormLabel>
          <div>This column type does not support filtering.</div>
        </div>
      );
    } else {
      children.push(
        <FormField
          key={`operator`}
          control={form.control}
          name={`${path}.operator`}
          render={({ field }) => (
            <FormItem>
              <FormLabel className="whitespace-pre"> </FormLabel>
              <FormControl>
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger className="min-w-[210px]">
                    <SelectValue placeholder="Select a fruit" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {operators.map((value: string) => {
                        return (
                          <SelectItem key={value} value={value}>
                            {Strings.startCase(value)}
                          </SelectItem>
                        );
                      })}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </FormControl>
              <FormDescription>{description}</FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
      );
    }
  }

  if (operator) {
    const dtype = columns[columnId];
    const operandSchemas = getSchemaForOperator(dtype, operator);
    if (operandSchemas.length === 1) {
      children.push(
        <React.Fragment key={`value`}>
          {renderZodSchema(operandSchemas[0], form, `${path}.value`)}
        </React.Fragment>
      );
    }
  }

  return (
    <FormField
      control={form.control}
      name={path}
      render={() => (
        <div className="flex flex-col gap-2 bg-red">
          <div className={cn("flex flex-row gap-3 items-start")}>
            {children}
          </div>
          <FormMessage />
        </div>
      )}
    />
  );
};
