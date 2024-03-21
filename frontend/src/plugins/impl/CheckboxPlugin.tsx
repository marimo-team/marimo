/* Copyright 2024 Marimo. All rights reserved. */
import { useId } from "react";
import { z } from "zod";

import { IPlugin, IPluginProps } from "../types";
import { Checkbox } from "../../components/ui/checkbox";
import { CheckedState } from "@radix-ui/react-checkbox";
import { Labeled } from "./common/labeled";

export class CheckboxPlugin
  implements IPlugin<boolean, { label: string | null }>
{
  tagName = "marimo-checkbox";

  validator = z.object({
    initialValue: z.boolean(),
    label: z.string().nullable(),
  });

  render(props: IPluginProps<boolean, { label: string | null }>): JSX.Element {
    return <CheckboxComponent {...props} />;
  }
}

const CheckboxComponent = ({
  value,
  setValue,
  data,
}: IPluginProps<boolean, { label: string | null }>): JSX.Element => {
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
      />
    </Labeled>
  );
};
