/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { z } from "zod";
import { DebouncedInput, DebouncedNumberInput } from "../ui/input";
import { Checkbox } from "../ui/checkbox";
import {
  type FieldValues,
  FormProvider,
  type Path,
  type UseFormReturn,
  useFieldArray,
} from "react-hook-form";
import {
  FormField,
  FormItem,
  FormLabel,
  FormControl,
  FormMessage,
  FormDescription,
} from "../ui/form";
import { Objects } from "../../utils/objects";
import { Button } from "../ui/button";
import { getDefaults, getUnionLiteral } from "./form-utils";
import { PlusIcon, RefreshCcw, Trash2Icon } from "lucide-react";
import { FieldOptions, randomNumber } from "@/components/forms/options";
import { cn } from "@/utils/cn";
import React from "react";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
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
import { Combobox, ComboboxItem } from "@/components/ui/combobox";
import { Events } from "@/utils/events";
import {
  TextAreaMultiSelect,
  ensureStringArray,
  SwitchableMultiSelect,
} from "./switchable-multi-select";
import { Textarea } from "../ui/textarea";
export interface FormRenderer<T extends FieldValues = any, S = any> {
  isMatch: (schema: z.ZodType) => schema is z.ZodType<S, z.ZodTypeDef, unknown>;
  Component: React.ComponentType<{
    schema: z.ZodType<S, z.ZodTypeDef, unknown>;
    form: UseFormReturn<T>;
    path: Path<T>;
  }>;
}

interface Props<T extends FieldValues> {
  form: UseFormReturn<T>;
  schema: z.ZodType;
  path?: Path<T>;
  renderers: Array<FormRenderer<T>> | undefined;
  children?: React.ReactNode;
}

export const ZodForm = <T extends FieldValues>({
  schema,
  form,
  path = "" as Path<T>,
  renderers = [],
  children,
}: Props<T>) => {
  return (
    <FormProvider {...form}>
      {children}
      {renderZodSchema(schema, form, path, renderers)}
    </FormProvider>
  );
};

export function renderZodSchema<T extends FieldValues, S>(
  schema: z.ZodType<S>,
  form: UseFormReturn<T>,
  path: Path<T>,
  renderers: Array<FormRenderer<T>>,
) {
  // Try custom renderers first
  for (const renderer of renderers) {
    const { isMatch, Component } = renderer;
    if (isMatch(schema)) {
      return <Component schema={schema} form={form} path={path} />;
    }
  }

  const {
    label,
    description,
    special,
    direction = "column",
  } = FieldOptions.parse(schema._def.description || "");

  if (schema instanceof z.ZodDefault) {
    let inner = schema._def.innerType as z.ZodType<unknown>;
    inner =
      !inner.description && schema.description
        ? inner.describe(schema.description)
        : inner;
    return renderZodSchema(inner, form, path, renderers);
  }

  if (schema instanceof z.ZodOptional) {
    let inner = schema._def.innerType as z.ZodType<unknown>;
    inner =
      !inner.description && schema.description
        ? inner.describe(schema.description)
        : inner;
    return renderZodSchema(inner, form, path, renderers);
  }

  if (schema instanceof z.ZodObject) {
    return (
      <div
        className={cn(
          "flex",
          direction === "row"
            ? "flex-row gap-6 items-start"
            : direction === "two-columns"
              ? "grid grid-cols-2 gap-y-6"
              : "flex-col gap-6",
        )}
      >
        <FormLabel>{label}</FormLabel>
        {Objects.entries(schema._def.shape()).map(([key, value]) => {
          const isLiteral = value instanceof z.ZodLiteral;
          const childForm = renderZodSchema(
            value as z.ZodType<unknown>,
            form,
            joinPath(path, key),
            renderers,
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
  }

  if (schema instanceof z.ZodString) {
    if (special === "time") {
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
                  type="time"
                  className="my-0"
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
      );
    }

    return <StringFormField schema={schema} form={form} path={path} />;
  }
  if (schema instanceof z.ZodBoolean) {
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
                  data-testid="marimo-plugin-data-frames-boolean-checkbox"
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
  }
  if (schema instanceof z.ZodNumber) {
    if (special === "random_number_button") {
      return (
        <FormField
          control={form.control}
          name={path}
          render={({ field }) => (
            <Button
              size="xs"
              data-testid="marimo-plugin-data-frames-random-number-button"
              variant="secondary"
              onClick={() => {
                field.onChange(randomNumber());
              }}
            >
              <RefreshCcw className="w-3.5 h-3.5 mr-1" />
              {label}
            </Button>
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
            <FormLabel>{label}</FormLabel>
            <FormDescription>{description}</FormDescription>
            <FormControl>
              <DebouncedNumberInput
                {...field}
                className="my-0"
                onValueChange={field.onChange}
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />
    );
  }
  if (schema instanceof z.ZodDate) {
    const inputType =
      special === "datetime"
        ? "datetime-local"
        : special === "time"
          ? "time"
          : "date";

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
                type={inputType}
                className="my-0"
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />
    );
  }
  if (schema instanceof z.ZodAny) {
    return <StringFormField schema={schema} form={form} path={path} />;
  }
  if (schema instanceof z.ZodEnum) {
    return (
      <SelectFormField
        schema={schema}
        form={form}
        path={path}
        options={schema._def.values}
      />
    );
  }
  if (schema instanceof z.ZodArray) {
    if (special === "text_area_multiline") {
      return <MultiStringFormField schema={schema} form={form} path={path} />;
    }

    // Inspect child type for a better input
    const childType = schema._def.type;

    // Show multi-select for enum array
    if (childType instanceof z.ZodEnum) {
      const childOptions: string[] = childType._def.values;
      return (
        <MultiSelectFormField
          schema={schema}
          form={form}
          path={path}
          itemLabel={label}
          options={childOptions}
        />
      );
    }

    // Fallback to generic array
    return (
      <div className="flex flex-col gap-1">
        <Label>{label}</Label>
        <FormArray
          schema={schema._def.type}
          form={form}
          path={path}
          key={path}
          minLength={schema._def.minLength?.value}
          renderers={renderers}
        />
      </div>
    );
  }

  if (schema instanceof z.ZodDiscriminatedUnion) {
    const options = schema._def.options as Array<z.ZodType<unknown>>;
    const discriminator = schema._def.discriminator;
    const optionsMap = schema._def.optionsMap;
    return (
      <FormField
        control={form.control}
        name={path}
        render={({ field }) => {
          const value = field.value;
          const types = options.map((option) => {
            return getUnionLiteral(option)._def.value;
          });

          const unionTypeValue: string =
            value && typeof value === "object" && discriminator in value
              ? value[discriminator]
              : types[0];

          const selectedOption = optionsMap.get(unionTypeValue) || options[0];

          return (
            <div className="flex flex-col">
              <FormLabel>{label}</FormLabel>
              <div className="flex border-b mb-4 -mt-2">
                {types.map((type: string) => (
                  <button
                    key={type}
                    type="button"
                    className={`px-4 py-2 ${
                      unionTypeValue === type
                        ? "border-b-2 border-primary font-medium"
                        : "text-muted-foreground"
                    }`}
                    onClick={() => {
                      const nextSchema = optionsMap.get(type);
                      if (nextSchema) {
                        field.onChange(getDefaults(nextSchema));
                      } else {
                        field.onChange({ [discriminator]: type });
                      }
                    }}
                  >
                    {type}
                  </button>
                ))}
              </div>
              <div className="flex flex-col" key={unionTypeValue}>
                {selectedOption &&
                  renderZodSchema(selectedOption, form, path, renderers)}
              </div>
            </div>
          );
        }}
      />
    );
  }
  if (schema instanceof z.ZodUnion) {
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

          const useTabs = special === "tabs";

          if (useTabs) {
            return (
              <div className="flex flex-col">
                <FormLabel>{label}</FormLabel>
                <div className="flex border-b mb-4 -mt-2">
                  {types.map((type: string) => (
                    <button
                      key={type}
                      type="button"
                      className={`px-4 py-2 ${
                        value === type
                          ? "border-b-2 border-primary font-medium"
                          : "text-muted-foreground"
                      }`}
                      onClick={() => field.onChange({ type })}
                    >
                      {type}
                    </button>
                  ))}
                </div>
                {selectedOption &&
                  renderZodSchema(selectedOption, form, path, renderers)}
              </div>
            );
          }

          return (
            <div className="flex flex-col mb-4 gap-1">
              <FormLabel>{label}</FormLabel>
              <NativeSelect
                data-testid="marimo-plugin-data-frames-union-select"
                {...field}
              >
                {types.map((type: string) => {
                  return (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  );
                })}
              </NativeSelect>
              {selectedOption &&
                renderZodSchema(selectedOption, form, path, renderers)}
            </div>
          );
        }}
      />
    );
  }

  if (schema instanceof z.ZodLiteral) {
    return (
      <FormField
        control={form.control}
        name={path}
        render={({ field }) => (
          <input {...field} type="hidden" value={schema._def.value} />
        )}
      />
    );
  }
  if (
    schema instanceof z.ZodEffects &&
    ["refinement", "transform"].includes(schema._def.effect.type)
  ) {
    return renderZodSchema(schema._def.schema, form, path, renderers);
  }

  return (
    <div>
      Unknown schema type{" "}
      {schema == null ? path : JSON.stringify(schema._type ?? schema)}
    </div>
  );
}

/**
 * Type: T[]
 */
const FormArray = ({
  schema,
  form,
  path,
  minLength,
  renderers,
}: {
  schema: z.ZodType<unknown>;
  form: UseFormReturn<any>;
  path: Path<any>;
  renderers: FormRenderer[];
  minLength?: number;
}) => {
  const { label, description } = FieldOptions.parse(
    schema._def.description || "",
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
            className="flex flex-row pl-2 ml-2 border-l-2 border-disabled hover-actions-parent relative pr-5 pt-1 items-center w-fit"
            key={field.id}
            onKeyDown={Events.onEnter((e) => e.preventDefault())}
          >
            {renderZodSchema(schema, form, `${path}[${index}]`, renderers)}
            {canRemove && (
              <Trash2Icon
                className="w-4 h-4 ml-2 my-1 text-muted-foreground hover:text-destructive cursor-pointer absolute right-0 top-5"
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
          data-testid="marimo-plugin-data-frames-add-array-item"
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

/**
 * Type: string
 */
const StringFormField = ({
  schema,
  form,
  path,
}: {
  schema: z.ZodAny | z.ZodString;
  form: UseFormReturn<any>;
  path: Path<any>;
}) => {
  const { label, description, placeholder, disabled, inputType } =
    FieldOptions.parse(schema._def.description);

  if (inputType === "textarea") {
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
                {...field}
                value={field.value}
                onChange={field.onChange}
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
              type={inputType}
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
};

/**
 * Type: string[]
 */
const MultiStringFormField = ({
  schema,
  form,
  path,
}: {
  schema: z.ZodAny | z.ZodString | z.ZodArray<any>;
  form: UseFormReturn<any>;
  path: Path<any>;
}) => {
  const { label, description, placeholder } = FieldOptions.parse(
    schema._def.description,
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
            <TextAreaMultiSelect {...field} placeholder={placeholder} />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  );
};

/**
 * Type: string
 * Known options
 */
const SelectFormField = ({
  schema,
  form,
  path,
  options,
  textTransform,
}: {
  schema: z.ZodEnum<any> | z.ZodString;
  form: UseFormReturn<any>;
  path: Path<any>;
  options: string[];
  textTransform?: (value: string) => string;
}) => {
  const { label, description, disabled, special } = FieldOptions.parse(
    schema._def.description,
  );

  if (special === "radio_group") {
    return (
      <FormField
        control={form.control}
        name={path}
        disabled={disabled}
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
                {options.map((value: string) => {
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
      disabled={disabled}
      render={({ field }) => (
        <FormItem>
          <FormLabel className="whitespace-pre">{label}</FormLabel>
          <FormDescription>{description}</FormDescription>
          <FormControl>
            <Select
              data-testid="marimo-plugin-data-frames-select"
              value={field.value}
              onValueChange={field.onChange}
            >
              <SelectTrigger className="min-w-[180px]">
                <SelectValue placeholder="--" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {options.map((value: string) => {
                    return (
                      <SelectItem key={value} value={value}>
                        {textTransform?.(value) ?? value}
                      </SelectItem>
                    );
                  })}
                  {options.length === 0 && (
                    <SelectItem disabled={true} value="--">
                      No options
                    </SelectItem>
                  )}
                </SelectGroup>
              </SelectContent>
            </Select>
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  );
};

/**
 * Type: string[]
 * Known options
 */
const MultiSelectFormField = ({
  schema,
  form,
  path,
  options,
  itemLabel,
  showSwitchable,
}: {
  schema: z.ZodEnum<any> | z.ZodString | z.ZodArray<any>;
  form: UseFormReturn<any>;
  path: Path<any>;
  itemLabel?: string;
  options: string[];
  showSwitchable?: boolean;
}) => {
  const { label, description, placeholder } = FieldOptions.parse(
    schema._def.description,
  );

  const resolvePlaceholder =
    placeholder ??
    (itemLabel ? `Select ${itemLabel?.toLowerCase()}` : undefined);

  return (
    <FormField
      control={form.control}
      name={path}
      render={({ field }) => {
        const valueAsArray = ensureStringArray(field.value);
        return (
          <FormItem>
            <FormLabel className="whitespace-pre">{label}</FormLabel>
            <FormDescription>{description}</FormDescription>
            <FormControl>
              {showSwitchable ? (
                <SwitchableMultiSelect
                  {...field}
                  value={valueAsArray}
                  options={options}
                  placeholder={resolvePlaceholder}
                />
              ) : (
                <Combobox
                  className="min-w-[180px]"
                  placeholder={resolvePlaceholder}
                  displayValue={(option: string) => Strings.startCase(option)}
                  multiple={true}
                  chips={true}
                  keepPopoverOpenOnSelect={true}
                  value={valueAsArray}
                  onValueChange={field.onChange}
                >
                  {options.map((option) => (
                    <ComboboxItem key={option} value={option}>
                      {option}
                    </ComboboxItem>
                  ))}
                </Combobox>
              )}
            </FormControl>
            <FormMessage />
          </FormItem>
        );
      }}
    />
  );
};

function joinPath<T>(...parts: Array<string | number>): Path<T> {
  return parts.filter((part) => part !== "").join(".") as Path<T>;
}
