/* Copyright 2024 Marimo. All rights reserved. */
import { useId } from "react";
import { z } from "zod";

import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import type { IPlugin, IPluginProps } from "@/plugins/types";
import { Labeled } from "./common/labeled";
import { cn } from "@/utils/cn";

/**
 * Arguments for a radio group
 *
 * @param label - a label for the group
 * @param options - text labels for each radio option
 */
interface Data {
  label: string | null;
  inline: boolean;
  options: string[];
  disabled?: boolean;
}

// The value is null when `initialValue` is null
type S = string | null;

export class RadioPlugin implements IPlugin<S, Data> {
  tagName = "marimo-radio";

  validator = z.object({
    initialValue: z.string().nullable(),
    inline: z.boolean().default(false),
    label: z.string().nullable(),
    options: z.array(z.string()),
    disabled: z.boolean().optional(),
  });

  render(props: IPluginProps<S, Data>): JSX.Element {
    return (
      <Radio {...props.data} value={props.value} setValue={props.setValue} />
    );
  }
}

interface RadioProps extends Data {
  value: S;
  setValue: (value: S) => void;
}

export const Radio = (props: RadioProps): JSX.Element => {
  const id = useId();

  return (
    <Labeled label={props.label} id={id} align={props.inline ? "left" : "top"}>
      <RadioGroup
        data-testid="marimo-plugin-radio"
        value={props.value ?? ""}
        onValueChange={props.setValue}
        className={cn(props.inline && "grid-flow-col gap-4")}
        aria-label="Radio Group"
        disabled={props.disabled}
      >
        {props.options.map((option, i) => (
          <div className="flex items-center space-x-2" key={i}>
            <RadioGroupItem value={option} id={`${id}-${i.toString()}`} />
            <Label
              htmlFor={`${id}-${i.toString()}`}
              className="text-sm font-normal"
            >
              {option}
            </Label>
          </div>
        ))}
      </RadioGroup>
    </Labeled>
  );
};
