/* Copyright 2023 Marimo. All rights reserved. */
import { useId } from "react";
import { z } from "zod";

import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { IPlugin, IPluginProps } from "@/plugins/types";
import * as labelStyles from "@/plugins/impl/Label.styles";
import { cn } from "@/lib/utils";
import { RenderHTML } from "../core/RenderHTML";

export class SwitchPlugin
  implements IPlugin<boolean, { label: string | null }>
{
  tagName = "marimo-switch";

  validator = z.object({
    initialValue: z.boolean(),
    label: z.string().nullable(),
  });

  render(props: IPluginProps<boolean, { label: string | null }>): JSX.Element {
    return <SwitchComponent {...props} />;
  }
}

const SwitchComponent = ({
  value,
  setValue,
  data,
}: IPluginProps<boolean, { label: string | null }>): JSX.Element => {
  const id = useId();
  const labelElement =
    data.label === null ? null : (
      <Label htmlFor={id} className="text-md">
        <RenderHTML html={data.label} />
      </Label>
    );

  return (
    <div
      className={cn(
        labelStyles.labelContainer,
        "align-middle",
        "items-start",
        "gap-x-2"
      )}
    >
      <Switch
        checked={value}
        onCheckedChange={setValue}
        id={id}
        className="data-[state=unchecked]:hover:bg-input/80"
      />
      {labelElement}
    </div>
  );
};
