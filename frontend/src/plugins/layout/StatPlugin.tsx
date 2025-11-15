/* Copyright 2024 Marimo. All rights reserved. */

import { TriangleIcon } from "lucide-react";
import type { JSX } from "react";
import { useLocale } from "react-aria";
import { z } from "zod";
import { cn } from "@/utils/cn";
import { prettyNumber } from "@/utils/numbers";
import type {
  IStatelessPlugin,
  IStatelessPluginProps,
} from "../stateless-plugin";

interface Data {
  value?: string | number | boolean | null;
  label?: string;
  caption?: string;
  bordered?: boolean;
  direction?: "increase" | "decrease";
  reverse_color?: boolean;
}

export class StatPlugin implements IStatelessPlugin<Data> {
  tagName = "marimo-stat";

  validator = z.object({
    value: z.union([z.string(), z.number(), z.boolean()]).optional(),
    label: z.string().optional(),
    caption: z.string().optional(),
    bordered: z.boolean().default(false),
    direction: z.enum(["increase", "decrease"]).optional(),
    reverse_color: z.boolean().default(false),
  });

  render({ data }: IStatelessPluginProps<Data>): JSX.Element {
    return <StatComponent {...data} />;
  }
}

export const StatComponent: React.FC<Data> = ({
  value,
  label,
  caption,
  bordered,
  direction,
  reverse_color,
}) => {
  const { locale } = useLocale();

  const renderPrettyValue = () => {
    if (value == null) {
      return <i>No value</i>;
    }

    if (typeof value === "string") {
      return value;
    }

    if (typeof value === "number") {
      return prettyNumber(value, locale);
    }

    if (typeof value === "boolean") {
      return value ? "True" : "False";
    }

    return String(value);
  };

  const fillColors = {
    increase: "var(--grass-8)",
    decrease: "var(--red-8)",
  };

  const strokeColors = {
    increase: "var(--grass-9)",
    decrease: "var(--red-9)",
  };

  return (
    <div
      className={cn(
        "text-card-foreground",
        bordered && "rounded-xl border shadow bg-card",
      )}
    >
      {label && (
        <div className="p-6 flex flex-row items-center justify-between space-y-0 pb-2">
          <h3 className="tracking-tight text-sm font-medium">{label}</h3>
        </div>
      )}
      <div className="p-6 pt-0">
        <div className="text-2xl font-bold">{renderPrettyValue()}</div>
        {caption && (
          <p className="pt-1 text-xs text-muted-foreground flex align-center">
            {direction === "increase" && (
              <TriangleIcon
                className="w-4 h-4 mr-1 p-0.5"
                fill={reverse_color ? fillColors.decrease : fillColors.increase}
                stroke={reverse_color ? strokeColors.decrease : strokeColors.increase}
              />
            )}
            {direction === "decrease" && (
              <TriangleIcon
                className="w-4 h-4 mr-1 p-0.5 transform rotate-180"
                fill={reverse_color ? fillColors.increase : fillColors.decrease}
                stroke={reverse_color ? strokeColors.increase : strokeColors.decrease}
              />
            )}
            {caption}
          </p>
        )}
      </div>
    </div>
  );
};
