/* Copyright 2023 Marimo. All rights reserved. */
import { useEffect, useState } from "react";
import { z } from "zod";

import { IPlugin, IPluginProps } from "@/plugins/types";
import { RefreshCwIcon } from "lucide-react";
import timestring from "timestring";
import { NativeSelect } from "@/components/ui/native-select";
import { Button } from "@/components/ui/button";

type Value = string | number | undefined;

interface Data {
  /**
   * The refresh interval in seconds.
   *
   * It may also be a human-readable string like "1m" or "1h" or "3h 30m".
   * These will be converted to seconds.
   */
  options: Array<string | number>;
  /**
   * The initial value.
   */
  defaultValue?: string | number;
}

export class RefreshPlugin implements IPlugin<Value, Data> {
  tagName = "marimo-refresh";

  validator = z.object({
    options: z.array(z.union([z.string(), z.number()])).default([]),
    defaultValue: z.union([z.string(), z.number()]).optional(),
  });

  render(props: IPluginProps<Value, Data>): JSX.Element {
    return <RefreshComponent {...props} />;
  }
}

const OFF = "off";

let count = 0;

const RefreshComponent = ({ setValue, data }: IPluginProps<Value, Data>) => {
  // internal selection
  const [selected, setSelected] = useState<string | number>(
    data.defaultValue ?? OFF
  );

  useEffect(() => {
    if (selected === OFF) {
      return;
    }

    const asSeconds =
      typeof selected === "number" ? selected : timestring(selected);

    const id = setInterval(
      () => setValue(() => `${selected} (${count++})`),
      asSeconds * 1000
    );
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);

  return (
    <span className="inline-flex items-center">
      <Button
        variant="outline"
        size="icon"
        className="border-0 shadow-none"
        onClick={() => setValue(() => `${selected} (${count++})`)}
      >
        <RefreshCwIcon className="w-4 h-4" />
      </Button>
      <NativeSelect
        onChange={(e) => {
          setSelected(e.target.value);
        }}
        value={selected}
        className="border-0 shadow-none"
      >
        <option value={OFF}>off</option>
        {data.options.map((option) => (
          <option value={option} key={option}>
            {typeof option === "number" ? `${option}s` : option}
          </option>
        ))}
      </NativeSelect>
    </span>
  );
};
