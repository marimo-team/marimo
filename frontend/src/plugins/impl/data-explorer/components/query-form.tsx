/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-base-to-string */
import { PrimitiveType, Schema } from "compassql/build/src/schema";
import React from "react";
import { Label } from "@/components/ui/label";
import { PRIMITIVE_TYPE_ICON } from "./icons";
import { useAtomValue } from "jotai";
import { chartSpecAtom, useChartSpecActions } from "../state/reducer";
import { EncodingChannel, FieldDefinition } from "../encoding";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  MULTI_TEMPORAL_FUNCTIONS,
  QUANTITATIVE_FUNCTIONS,
  SINGLE_TEMPORAL_FUNCTIONS,
} from "../functions/function";
import { FieldFunction } from "../functions/types";
import { FunctionSquareIcon } from "lucide-react";
import { startCase } from "lodash-es";
import { ExpandedType } from "compassql/build/src/query/expandedtype";
import { MARKS, SpecMark } from "../marks";
import { SHORT_WILDCARD } from "compassql/build/src/wildcard";

interface Props {
  schema: Schema;
  mark: SpecMark;
}

const ENCODINGS: EncodingChannel[] = ["x", "y", "row", "column"];

const MARK_ENCODINGS: EncodingChannel[] = ["color", "size", "shape"];

/**
 * Query form component that allows users to select encodings
 * for the chart spec.
 */
export const QueryForm: React.FC<Props> = ({ schema, mark }) => {
  const value = useAtomValue(chartSpecAtom);
  const actions = useChartSpecActions();
  const canConfigureRowOrColumn = value.encoding.x && value.encoding.y;

  const renderChannel = (channel: EncodingChannel) => {
    const isRowOrColumn = channel === "row" || channel === "column";
    const disabled = isRowOrColumn && !canConfigureRowOrColumn;

    return (
      <FieldSelect
        key={channel}
        schema={schema}
        label={channel}
        disabled={disabled}
        fieldDefinition={value.encoding[channel]}
        onChange={(value) => actions.setEncoding({ [channel]: value })}
      />
    );
  };

  const markSelect = (
    <Select
      data-testid="marimo-plugin-data-explorer-mark-select"
      value={mark.toString()}
      onValueChange={(value) => actions.setMark(value as SpecMark)}
    >
      <SelectTrigger>
        <SelectValue placeholder="Mark" />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          <SelectLabel>Mark</SelectLabel>
          {MARKS.map((mark) => (
            <SelectItem key={mark} value={mark}>
              {mark === SHORT_WILDCARD ? "auto" : mark}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  );

  return (
    <div className="grid gap-x-2 gap-y-4 justify-items-start py-3 pl-4 pr-2 bg-[var(--slate-1)] border rounded items-center grid-template-columns-[repeat(2,_minmax(0,_min-content))] self-start">
      <span className="col-span-2 flex items-center justify-between w-full">
        <div className="text-sm font-semibold">Encodings</div>
      </span>
      {ENCODINGS.map(renderChannel)}
      <span className="col-span-2 text-sm font-semibold w-full border-t border-divider flex items-center justify-between pt-2 pr-[30px]">
        <div>Mark</div>
        {markSelect}
      </span>
      {MARK_ENCODINGS.map(renderChannel)}
    </div>
  );
};

/**
 * Select dropdown to choose a field
 */
const FieldSelect = ({
  label,
  schema,
  fieldDefinition,
  disabled,
  onChange,
}: {
  label: string;
  schema: Schema;
  disabled: boolean;
  fieldDefinition: FieldDefinition | undefined;
  onChange: (def: FieldDefinition | undefined) => void;
}) => {
  const renderValue = () => {
    if (!fieldDefinition) {
      return "--";
    }

    if (fieldDefinition.field === "*") {
      return (
        <span className="flex gap-2 flex-1">
          {PRIMITIVE_TYPE_ICON[PrimitiveType.NUMBER]}
          <span className="text-left flex-1">Count</span>
        </span>
      );
    }

    const field = fieldDefinition.field.toString();
    const renderLabel = () => {
      if (fieldDefinition.fn) {
        return `${fieldDefinition.fn}(${fieldDefinition.field})`;
      }

      return field;
    };

    return (
      <span className="flex gap-2 flex-1">
        {PRIMITIVE_TYPE_ICON[schema.primitiveType(field)]}
        <span className="text-left flex-1">{renderLabel()}</span>
      </span>
    );
  };

  const clear = () => {
    onChange(undefined);
  };

  const field = fieldDefinition?.field.toString() ?? "";

  return (
    <>
      <Label className="text-[var(--slate-11)] font-semibold">{label}</Label>
      <div className="flex flex-row gap-1 h-[26px]">
        <Select
          value={field}
          disabled={disabled}
          onValueChange={(value) => {
            if (value === "*") {
              onChange({
                field: "*",
                fn: "count",
                type: "quantitative",
              });
            } else {
              onChange({
                field: value,
                type: schema.vlType(value),
              });
            }
          }}
        >
          <SelectTrigger
            className="min-w-[140px] lg:min-w-[210px] h-full"
            onClear={field ? clear : undefined}
          >
            {renderValue()}
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {schema.fieldNames().map((name) => {
                return (
                  <SelectItem key={name} value={name.toString()}>
                    <span className="flex items-center gap-2 flex-1">
                      {PRIMITIVE_TYPE_ICON[schema.primitiveType(name)]}
                      <span className="flex-1">{name}</span>
                      <span className="text-muted-foreground text-xs font-semibold">
                        ({schema.vlType(name)})
                      </span>
                    </span>
                  </SelectItem>
                );
              })}
              {schema.fieldNames().length === 0 && (
                <SelectItem disabled={true} value="--">
                  No columns
                </SelectItem>
              )}
              <SelectSeparator />
              <SelectItem key={"*"} value={"*"}>
                <span className="flex items-center gap-1 flex-1">
                  {PRIMITIVE_TYPE_ICON[PrimitiveType.NUMBER]}
                  <span className="flex-1">Count</span>
                </span>
              </SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>
        <div className="w-[26px]">
          {fieldDefinition && (
            <FieldOptions field={fieldDefinition} onChange={onChange} />
          )}
        </div>
      </div>
    </>
  );
};

const NONE_FN = "__";

/**
 * Field options. Currently only changes the fields aggregate/time functions.
 */
const FieldOptions = ({
  field,
  onChange,
}: {
  field: FieldDefinition;
  onChange: (def: FieldDefinition | undefined) => void;
}) => {
  if (field.field === "*") {
    return null;
  }

  let options: Array<[string, FieldFunction[]]> = [];

  if (field.type === ExpandedType.QUANTITATIVE) {
    options = [["", QUANTITATIVE_FUNCTIONS]];
  }

  if (field.type === ExpandedType.TEMPORAL) {
    options = [
      ["Single", SINGLE_TEMPORAL_FUNCTIONS],
      ["Multi", MULTI_TEMPORAL_FUNCTIONS],
    ];
  }

  if (options.length > 0) {
    return (
      <Select
        data-testid="marimo-plugin-data-explorer-field-options"
        value={field.fn}
        onValueChange={(value) => {
          onChange({
            ...field,
            fn: value === NONE_FN ? undefined : (value as FieldFunction),
          });
        }}
      >
        <SelectTrigger
          className="h-full px-1"
          hideChevron={true}
          variant="ghost"
        >
          <FunctionSquareIcon size={14} strokeWidth={1.5} />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem value={NONE_FN}>None</SelectItem>
          </SelectGroup>
          <SelectSeparator />
          {options.map(([label, fns]) => {
            return (
              <SelectGroup key={label}>
                {label && <SelectLabel>{label}</SelectLabel>}
                {fns.map((fn) => (
                  <SelectItem key={fn} value={fn ?? NONE_FN}>
                    {startCase(fn)}
                  </SelectItem>
                ))}
              </SelectGroup>
            );
          })}
        </SelectContent>
      </Select>
    );
  }

  return null;
};
