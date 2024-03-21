/* Copyright 2024 Marimo. All rights reserved. */
import { useEffect, useState } from "react";
import { z } from "zod";

import { IPlugin, IPluginProps } from "@/plugins/types";
import { RefreshCwIcon } from "lucide-react";
import timestring from "timestring";
import { NativeSelect } from "@/components/ui/native-select";
import { Button } from "@/components/ui/button";
import { useEvent } from "../../hooks/useEvent";
import { cn } from "@/utils/cn";
import { Labeled } from "./common/labeled";

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
  defaultInterval?: string | number;

  label?: string | null;
}

const MIN_INTERVAL = 0.1;

const zodTimestring = z.string().superRefine((s, ctx) => {
  try {
    const seconds = timestring(s);
    if (seconds < MIN_INTERVAL) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Must be greater than ${MIN_INTERVAL} seconds.`,
      });
    }
    return;
  } catch {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Must be a valid timestring. e.g. 1m, 30m, 1h.",
    });
    return;
  }
});

export class RefreshPlugin implements IPlugin<Value, Data> {
  tagName = "marimo-refresh";

  validator = z.object({
    options: z
      .array(z.union([zodTimestring, z.number().min(MIN_INTERVAL)]))
      .default([]),
    defaultInterval: z
      .union([zodTimestring, z.number().min(MIN_INTERVAL)])
      .optional(),
    label: z.string().nullable(),
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
    data.defaultInterval ?? OFF,
  );

  // reset selection when defaultInterval changes
  useEffect(() => {
    setSelected(data.defaultInterval ?? OFF);
  }, [data.defaultInterval]);

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

    let asSeconds =
      typeof selected === "number"
        ? selected
        : /[a-z]/.test(selected) // check if has units
          ? timestring(selected)
          : timestring(`${selected}s`); // default to seconds if no units

    // Smallest interval is 1 second
    asSeconds = Math.max(asSeconds, 1);

    const id = setInterval(refresh, asSeconds * 1000);
    return () => clearInterval(id);
  }, [selected, refresh]);

  const noShadow =
    "shadow-none! hover:shadow-none! focus:shadow-none! active:shadow-none!";

  const hasOptions = data.options.length > 0;

  return (
    <Labeled label={data.label}>
      <span className="inline-flex items-center text-secondary-foreground rounded shadow-smSolid">
        <Button
          data-testid="marimo-plugin-refresh-button"
          variant="secondary"
          size="icon"
          className={cn(
            noShadow,
            "border mb-0 rounded",
            hasOptions && "border-r-0 rounded-tr-none rounded-br-none",
          )}
          onClick={refresh}
        >
          <RefreshCwIcon
            className={cn("w-3.5 h-3.5", spin && "animate-spin")}
          />
        </Button>
        <NativeSelect
          data-testid="marimo-plugin-refresh-select"
          onChange={(e) => {
            setSelected(e.target.value);
          }}
          value={selected}
          className={cn(
            noShadow,
            "border mb-0 bg-secondary rounded rounded-tl-none rounded-bl-none hover:bg-secondary/60",
            !hasOptions && "hidden",
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
    </Labeled>
  );
};
