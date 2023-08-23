/* Copyright 2023 Marimo. All rights reserved. */
import { useEffect, useState } from "react";
import { z } from "zod";

import { IPlugin, IPluginProps } from "@/plugins/types";
import { RefreshCwIcon } from "lucide-react";
import timestring from "timestring";
import { NativeSelect } from "@/components/ui/native-select";
import { Button } from "@/components/ui/button";
import { useEvent } from "../../hooks/useEvent";
import { cn } from "@/lib/utils";

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
  const [spin, setSpin] = useState(false);

  const refresh = useEvent(() => {
    setSpin(true);
    setValue(() => `${selected} (${count++})`);
    setTimeout(() => setSpin(false), 500); // spin for 500ms
  });

  useEffect(() => {
    if (selected === OFF) {
      return;
    }

    const asSeconds =
      typeof selected === "number" ? selected : timestring(selected);

    const id = setInterval(refresh, asSeconds * 1000);
    return () => clearInterval(id);
  }, [selected, refresh]);

  const noShadow =
    "shadow-none! hover:shadow-none! focus:shadow-none! active:shadow-none!";

  return (
    <span className="inline-flex items-center text-secondary-foreground rounded shadow-smSolid">
      <Button
        variant="secondary"
        size="icon"
        className={cn(
          noShadow,
          "border mb-0 border-r-0 rounded-tr-none rounded-br-none"
        )}
        onClick={refresh}
      >
        <RefreshCwIcon className={cn("w-3.5 h-3.5", spin && "animate-spin")} />
      </Button>
      <NativeSelect
        onChange={(e) => {
          setSelected(e.target.value);
        }}
        value={selected}
        className={cn(
          noShadow,
          "border mb-0 bg-secondary rounded-tl-none rounded-bl-none hover:bg-secondary/60"
        )}
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
