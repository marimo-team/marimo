/* Copyright 2024 Marimo. All rights reserved. */
import { useId } from "react";
import { z } from "zod";

import type { IPlugin, IPluginProps } from "../types";
import { Checkbox } from "../../components/ui/checkbox";
import type { CheckedState } from "@radix-ui/react-checkbox";
import { Labeled } from "./common/labeled";

type T = boolean;

interface Data {
  label: string | null;
  disabled?: boolean;
}

export class CheckboxPlugin implements IPlugin<T, Data> {
  tagName = "marimo-checkbox";

  validator = z.object({
    initialValue: z.boolean(),
    label: z.string().nullable(),
    disabled: z.boolean().optional(),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return <CheckboxComponent {...props} />;
  }
}

const CheckboxComponent = ({
  value,
  setValue,
  data,
}: IPluginProps<T, Data>): JSX.Element => {
  const onClick = (newValue: CheckedState) => {
    // unsupported state
    if (newValue === "indeterminate") {
      return;
    }
    setValue(newValue);
  };
  const id = useId();

  return (
    <Labeled label={data.label} align="right" id={id}>
      <Checkbox
        data-testid="marimo-plugin-checkbox"
        checked={value}
        onCheckedChange={onClick}
        id={id}
        disabled={data.disabled}
      />
    </Labeled>
  );
};
