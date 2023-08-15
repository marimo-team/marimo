/* Copyright 2023 Marimo. All rights reserved. */
import { useId } from "react";
import { z } from "zod";

import { IPlugin, IPluginProps } from "../types";
import * as labelStyles from "./Label.styles";
import { Checkbox } from "../../components/ui/checkbox";
import { Label } from "../../components/ui/label";
import { CheckedState } from "@radix-ui/react-checkbox";
import { renderHTML } from "../core/RenderHTML";

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
  const labelElement =
    data.label === null ? null : (
      <Label htmlFor={id} className="text-md">
        {renderHTML({ html: data.label })}
      </Label>
    );

  return (
    <div className={`${labelStyles.labelContainer} align-middle`}>
      <Checkbox checked={value} onCheckedChange={onClick} id={id} />
      {labelElement}
    </div>
  );
};
