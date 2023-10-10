/* Copyright 2023 Marimo. All rights reserved. */
import clsx from "clsx";
import { useId } from "react";
import { z } from "zod";

import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { IPlugin, IPluginProps } from "@/plugins/types";
import { Labeled } from "./common/labeled";

/**
 * Arguments for a radio group
 *
 * @param label - a label for the group
 * @param options - text labels for each radio option
 */
interface Data {
  label?: string | null;
  options: string[];
}

// The value is null when `initialValue` is null
type S = string | null;

export class RadioPlugin implements IPlugin<S, Data> {
  tagName = "marimo-radio";

  validator = z.object({
    initialValue: z.string().nullable(),
    label: z.string().nullish(),
    options: z.array(z.string()),
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

const Radio = (props: RadioProps): JSX.Element => {
  const id = useId();

  return (
    <Labeled label={props.label} id={id} align="top">
      <RadioGroup
        value={props.value ?? ""}
        onValueChange={props.setValue}
        aria-label="Radio Group"
      >
        {props.options.map((option, i) => (
          <div className="flex items-center space-x-3" key={i}>
            <RadioGroupItem value={option} id={`${id}-${i.toString()}`} />
            <Label
              htmlFor={`${id}-${i.toString()}`}
              className={clsx(
                "text-md",
                option === props.value ? "font-semibold" : ""
              )}
            >
              {option}
            </Label>
          </div>
        ))}
      </RadioGroup>
    </Labeled>
  );
};
