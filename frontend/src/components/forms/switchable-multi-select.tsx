/* Copyright 2024 Marimo. All rights reserved. */

import { EditIcon } from "lucide-react";
import React, { useState } from "react";
import { cn } from "@/utils/cn";
import { Combobox, ComboboxItem } from "../ui/combobox";
import { Textarea } from "../ui/textarea";
import { Toggle } from "../ui/toggle";
import { Tooltip } from "../ui/tooltip";

interface Props {
  options: string[];
  value: string[];
  className?: string;
  placeholder?: string;
  comboBoxClassName?: string;
  textAreaClassName?: string;
  onChange: (value: string[] | null) => void;
}

// new-line separated
const DELIMINATOR = "\n";

/**
 * Switch between multi-select options or using a textarea.
 */
export const SwitchableMultiSelect: React.FC<Props> = ({
  value,
  options,
  onChange,
  className,
  placeholder,
  textAreaClassName,
  comboBoxClassName,
}) => {
  const [showTextArea, setShowTextArea] = useState(false);
  const valueAsArray = ensureStringArray(value);

  const renderInput = () => {
    if (showTextArea) {
      return (
        <TextAreaMultiSelect
          value={valueAsArray}
          className={textAreaClassName}
          onChange={onChange}
          placeholder={
            placeholder ? `${placeholder}: one per line` : "One value per line"
          }
        />
      );
    }

    return (
      <Combobox
        placeholder={placeholder}
        displayValue={(option: string) => option}
        className={cn("w-full max-w-[400px]", comboBoxClassName)}
        multiple={true}
        value={valueAsArray}
        onValueChange={onChange}
        keepPopoverOpenOnSelect={true}
        chips={true}
        chipsClassName="flex-row flex-wrap min-w-[210px]"
      >
        {options.map((option) => (
          <ComboboxItem key={option} value={option}>
            {option}
          </ComboboxItem>
        ))}
      </Combobox>
    );
  };

  return (
    <div className={cn("flex gap-1", className)}>
      {renderInput()}
      <Tooltip
        content={showTextArea ? "Switch to multi-select" : "Switch to textarea"}
      >
        <Toggle
          size="xs"
          onPressedChange={setShowTextArea}
          pressed={showTextArea}
        >
          <EditIcon className="w-3 h-3" />
        </Toggle>
      </Tooltip>
    </div>
  );
};

/**
 * Treat a textarea as a multi-select,
 * where each line is a value.
 */
export const TextAreaMultiSelect: React.FC<{
  value: string[];
  onChange: (value: string[]) => void;
  className?: string;
  placeholder?: string;
}> = (props) => {
  const { className, value, onChange, placeholder } = props;
  const valueAsArray = ensureStringArray(value);
  return (
    <Textarea
      value={valueAsArray.join(DELIMINATOR)}
      className={className}
      rows={4}
      onChange={(e) => {
        if (e.target.value === "") {
          onChange([]);
          return;
        }
        onChange(e.target.value.split(DELIMINATOR));
      }}
      placeholder={
        placeholder ? `${placeholder}: one per line` : "One value per line"
      }
    />
  );
};

export function ensureStringArray<T extends string>(
  value: T | T[] | null | undefined,
): T[] {
  if (value == null) {
    return [];
  }

  if (Array.isArray(value)) {
    return value;
  }
  return [value].filter((v) => v != null || v !== "");
}
