/* Copyright 2024 Marimo. All rights reserved. */
import { useId } from "react";
import { z } from "zod";

import { Switch } from "@/components/ui/switch";
import type { IPlugin, IPluginProps } from "@/plugins/types";
import { Labeled } from "./common/labeled";

type T = boolean;
interface Data {
  label: string | null;
  disabled?: boolean;
}

export class SwitchPlugin implements IPlugin<T, Data> {
  tagName = "marimo-switch";

  validator = z.object({
    initialValue: z.boolean(),
    label: z.string().nullable(),
    disabled: z.boolean().optional(),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return <SwitchComponent {...props} />;
  }
}

const SwitchComponent = ({
  value,
  setValue,
  data,
}: IPluginProps<T, Data>): JSX.Element => {
  const id = useId();

  return (
    <Labeled label={data.label} align="right" id={id} labelClassName="ml-1">
      <Switch
        data-testid="marimo-plugin-switch"
        checked={value}
        onCheckedChange={setValue}
        id={id}
        className="data-[state=unchecked]:hover:bg-input/80 mb-0"
        disabled={data.disabled}
      />
    </Labeled>
  );
};
