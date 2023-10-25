/* Copyright 2023 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { z } from "zod";
import {
  DebouncedInput,
  DebouncedNumberInput,
  Input,
} from "../../../../components/ui/input";
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
  FormMessageTooltip,
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
import { DataTypeIcon } from "./datatype-icon";
import { Events } from "@/utils/events";

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
          direction === "row" ? "flex-row gap-6 items-start" : "flex-col gap-6"
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
            <FormDescription>{description}</FormDescription>
            <FormControl>
              <DebouncedInput
                {...field}
                value={field.value}
                onValueChange={field.onChange}
                className="my-0"
                placeholder={placeholder}
                disabled={disabled}
              />
            </FormControl>
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
              <FormDescription>{description}</FormDescription>
              <FormControl>
                <Checkbox
                  checked={field.value}
                  onCheckedChange={field.onChange}
                />
              </FormControl>
            </div>
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
            <FormDescription>{description}</FormDescription>
            <FormControl>
              <DebouncedNumberInput
                {...field}
                type="number"
                className="my-0"
                onValueChange={field.onChange}
              />
            </FormControl>
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
            <FormDescription>{description}</FormDescription>
            <FormControl>
              <DebouncedInput
                {...field}
                onValueChange={field.onChange}
                type="date"
                className="my-0"
              />
            </FormControl>
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
            <FormDescription>{description}</FormDescription>
            <FormControl>
              <DebouncedInput
                {...field}
                onValueChange={field.onChange}
                className="my-0"
              />
            </FormControl>
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
              <FormDescription>{description}</FormDescription>
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
            <FormDescription>{description}</FormDescription>
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
              <FormDescription>{description}</FormDescription>
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
          minLength={schema._def.minLength?.value}
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
        render={({ field }) => <input {...field} type="hidden" />}
      />
    );
  } else if (
    schema instanceof z.ZodEffects &&
    ["refinement", "transform"].includes(schema._def.effect.type)
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
            <FormDescription>{description}</FormDescription>
            <FormMessage />
            <FormControl>
              <Input {...field} className="my-0" />
            </FormControl>
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

const StyledFormMessage = ({ className }: { className?: string }) => {
  return (
    <FormMessageTooltip
      className={cn(
        "absolute -left-6 bottom-0 text-destructive text-xs w-[16px]",
        className
      )}
    />
  );
};

const FormArray = ({
  schema,
  form,
  path,
  minLength,
}: {
  schema: z.ZodType<unknown>;
  form: UseFormReturn<any>;
  path: Path<any>;
  minLength?: number;
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

  const isBelowMinLength = minLength != null && fields.length < minLength;
  const canRemove = minLength == null || fields.length > minLength;

  return (
    <div className="flex flex-col gap-2 min-w-[220px]">
      <FormLabel>{label}</FormLabel>
      <FormDescription>{description}</FormDescription>
      {fields.map((field, index) => {
        return (
          <div
            className="flex flex-row pl-2 ml-4 border-l-2 border-disabled hover-actions-parent relative pr-5 pt-1 items-center w-fit"
            key={field.id}
            onKeyDown={Events.onEnter((e) => e.preventDefault())}
          >
            {renderZodSchema(schema, form, `${path}[${index}]`)}
            {canRemove && (
              <Trash2Icon
                className="w-4 h-4 ml-2 my-1 text-muted-foreground hover-action hover:text-destructive cursor-pointer absolute right-0 bottom-0"
                onClick={() => {
                  remove(index);
                }}
              />
            )}
          </div>
        );
      })}
      {isBelowMinLength && (
        <div className="text-destructive text-xs font-semibold">
          <div>At least {minLength} required.</div>
        </div>
      )}
      <div>
        <Button
          size="xs"
          variant="text"
          className="hover:text-accent-foreground"
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
  onChange,
}: {
  schema: z.ZodString;
  form: UseFormReturn<any>;
  path: Path<any>;
  onChange?: (value: string) => void;
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
          <FormDescription>{description}</FormDescription>
          <StyledFormMessage />
          <FormControl>
            <Select
              value={field.value}
              onValueChange={(value) => {
                onChange?.(value);
                field.onChange(value);
              }}
            >
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
      onChange={(value) => {
        // Reset operator and value if the column type changes
        const currentDtype = columns[columnId];
        const nextDtype = columns[value];
        if (nextDtype !== currentDtype) {
          form.setValue(`${path}.value`, undefined);
        }
      }}
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
              <FormDescription>{description}</FormDescription>
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
          <div className={cn("flex flex-row gap-3 items-center")}>
            {children}
          </div>
          <FormMessage />
        </div>
      )}
    />
  );
};
