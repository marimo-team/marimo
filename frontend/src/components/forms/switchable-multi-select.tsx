/* Copyright 2023 Marimo. All rights reserved. */
import React, { useState } from "react";
import { Textarea } from "../ui/textarea";
import { Combobox, ComboboxItem } from "../ui/combobox";
import { Tooltip } from "../ui/tooltip";
import { EditIcon } from "lucide-react";
import { Toggle } from "../ui/toggle";
import { cn } from "@/lib/utils";

interface Props {
  options: string[];
  value: string[];
  className?: string;
  placeholder?: string;
  comboBoxClassName?: string;
  textAreaClassName?: string;
  onChange: (value: string[]) => void;
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
  const valueAsArray = Array.isArray(value) ? value : [value];

  const renderInput = () => {
    if (showTextArea) {
      return (
        <Textarea
          value={valueAsArray.join(DELIMINATOR)}
          className={textAreaClassName}
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
    }

    return (
      <Combobox
        placeholder={placeholder}
        displayValue={(option: string) => option}
        className={comboBoxClassName}
        multiple={true}
        value={valueAsArray}
        onValueChange={onChange}
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
