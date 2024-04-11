/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { z } from "zod";
import {
  DebouncedInput,
  DebouncedNumberInput,
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
import { PlusIcon, RefreshCcw, Trash2Icon } from "lucide-react";
import {
  FieldOptions,
  randomNumber,
} from "@/plugins/impl/data-frames/forms/options";
import { cn } from "@/utils/cn";
import React, { useContext, useEffect } from "react";
import {
  ColumnFetchValuesContext,
  ColumnInfoContext,
  ColumnNameContext,
} from "@/plugins/impl/data-frames/forms/context";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { getOperatorForDtype, getSchemaForOperator } from "../utils/operators";
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
import { useAsyncData } from "@/hooks/useAsyncData";
import { Combobox, ComboboxItem } from "@/components/ui/combobox";
import {
  SwitchableMultiSelect,
  TextAreaMultiSelect,
  ensureStringArray,
} from "@/components/forms/switchable-multi-select";

interface Props<T extends FieldValues> {
  form: UseFormReturn<T>;
  schema: z.ZodType;
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
  path: Path<T>,
) {
  const {
    label,
    description,
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
          direction === "row" ? "flex-row gap-6 items-start" : "flex-col gap-6",
        )}
      >
        <FormLabel>{label}</FormLabel>
        {Objects.entries(schema._def.shape()).map(([key, value]) => {
          const isLiteral = value instanceof z.ZodLiteral;
          const childForm = renderZodSchema(
            value as z.ZodType<unknown>,
            form,
            `${path}.${key}` as Path<T>,
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
      return <ColumnFormField schema={schema} form={form} path={path} />;
    }

    if (special === "column_values") {
      return <ColumnValuesFormField schema={schema} form={form} path={path} />;
    }

    return <StringFormField schema={schema} form={form} path={path} />;
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
  } else if (schema instanceof z.ZodNumber) {
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
    return <StringFormField schema={schema} form={form} path={path} />;
  } else if (schema instanceof z.ZodEnum) {
    return (
      <SelectFormField
        schema={schema}
        form={form}
        path={path}
        options={schema._def.values}
      />
    );
  } else if (schema instanceof z.ZodArray) {
    if (special === "text_area_multiline") {
      return <MultiStringFormField schema={schema} form={form} path={path} />;
    }
    if (special === "column_values") {
      return (
        <MultiColumnValuesFormField schema={schema} form={form} path={path} />
      );
    }

    // Inspect child type for a better input
    const childType = schema._def.type;
    const childSpecial = FieldOptions.parse(childType._def.description).special;

    // Show column multi-select for array with column_id
    if (childType instanceof z.ZodString && childSpecial === "column_id") {
      return (
        <MultiColumnFormField
          schema={childType}
          form={form}
          path={path}
          itemLabel={label}
        />
      );
    }

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
        className,
      )}
    />
  );
};

/**
 * Type: T[]
 */
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
            className="flex flex-row pl-2 ml-4 border-l-2 border-disabled hover-actions-parent relative pr-5 pt-1 items-center w-fit"
            key={field.id}
            onKeyDown={Events.onEnter((e) => e.preventDefault())}
          >
            {renderZodSchema(schema, form, `${path}[${index}]`)}
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
 * Special: column_id
 */
const ColumnFormField = ({
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
  const columns = useContext(ColumnInfoContext);
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
              data-testid="marimo-plugin-data-frames-column-select"
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
                  {Objects.keys(columns).length === 0 && (
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
};

/**
 * Type: string[]
 * Special: column_ids
 */
const MultiColumnFormField = ({
  schema,
  form,
  path,
  itemLabel,
}: {
  schema: z.ZodString;
  form: UseFormReturn<any>;
  path: Path<any>;
  itemLabel?: string;
}) => {
  const columns = useContext(ColumnInfoContext);
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
              <Combobox
                className="min-w-[210px]"
                placeholder={placeholder}
                displayValue={(option: string) => option}
                multiple={true}
                chips={true}
                keepPopoverOpenOnSelect={true}
                value={values}
                onValueChange={(v) => {
                  field.onChange(v);
                }}
              >
                {Objects.entries(columns).map(([name, dtype]) => {
                  return (
                    <ComboboxItem key={name} value={name.toString()}>
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

/**
 * Type: { column_id: string; operator: string; value: any }
 * Special: column_filter
 */
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
  const columns = useContext(ColumnInfoContext);
  const { field } = useController({ name: path });

  const columnIdSchema = Objects.entries(schema._def.shape()).find(
    ([key, value]) => {
      return key === "column_id";
    },
  )?.[1] as unknown as z.ZodString;

  // existing values
  const { column_id: columnId, operator } = field.value || {};

  const children = [
    <ColumnFormField
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
        </div>,
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
                <Select
                  data-testid="marimo-plugin-data-frames-filter-operator-select"
                  value={field.value}
                  onValueChange={field.onChange}
                >
                  <SelectTrigger className="min-w-[210px]">
                    <SelectValue placeholder="--" />
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
        />,
      );
    }
  }

  if (operator) {
    const dtype = columns[columnId];
    const operandSchemas = getSchemaForOperator(dtype, operator);
    if (operandSchemas.length === 1) {
      children.push(
        <React.Fragment key={`value`}>
          <ColumnNameContext.Provider value={columnId}>
            {renderZodSchema(operandSchemas[0], form, `${path}.value`)}
          </ColumnNameContext.Provider>
        </React.Fragment>,
      );
    }
  }

  return (
    <FormField
      control={form.control}
      name={path}
      render={() => (
        <div className="flex flex-col gap-2 bg-red">
          <div className={cn("flex flex-row gap-3")}>{children}</div>
          <FormMessage />
        </div>
      )}
    />
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
  const { label, description, placeholder, disabled } = FieldOptions.parse(
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
              <SelectTrigger className="min-w-[210px]">
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
                  className="min-w-[210px]"
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

/**
 * Type: string
 * Special: column_values
 */
const ColumnValuesFormField = ({
  schema,
  form,
  path,
}: {
  schema: z.ZodString;
  form: UseFormReturn<any>;
  path: Path<any>;
}) => {
  const { label, description, placeholder } = FieldOptions.parse(
    schema._def.description,
  );
  const column = useContext(ColumnNameContext);
  const fetchValues = useContext(ColumnFetchValuesContext);
  const { data, loading } = useAsyncData(() => {
    return fetchValues({ column });
  }, [column]);

  const options = data?.values || [];

  // loaded with no options
  if (options.length === 0 && !loading) {
    return <StringFormField schema={schema} form={form} path={path} />;
  }

  const optionsAsStrings = options.map(String);
  return (
    <FormField
      control={form.control}
      name={path}
      render={({ field }) => {
        return (
          <FormItem>
            <FormLabel className="whitespace-pre">{label}</FormLabel>
            <FormDescription>{description}</FormDescription>
            <FormControl>
              <Combobox
                className="min-w-[210px]"
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
        );
      }}
    />
  );
};

/**
 * Type: string[]
 * Special: column_values
 */
const MultiColumnValuesFormField = ({
  schema,
  form,
  path,
}: {
  schema: z.ZodString | z.ZodArray<any>;
  form: UseFormReturn<any>;
  path: Path<any>;
}) => {
  const column = useContext(ColumnNameContext);
  const fetchValues = useContext(ColumnFetchValuesContext);
  const { data, loading } = useAsyncData(() => {
    return fetchValues({ column });
  }, [column]);

  const options = data?.values || [];

  // loaded with no options
  if (options.length === 0 && !loading) {
    return <MultiStringFormField schema={schema} form={form} path={path} />;
  }

  const optionsAsStrings = options.map(String);
  return (
    <MultiSelectFormField
      schema={schema}
      form={form}
      path={path}
      showSwitchable={true}
      options={optionsAsStrings}
    />
  );
};
