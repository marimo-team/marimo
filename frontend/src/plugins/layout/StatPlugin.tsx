/* Copyright 2026 Marimo. All rights reserved. */

import { TriangleIcon } from "lucide-react";
import type { JSX } from "react";
import { useLocale } from "react-aria";
import { z } from "zod";
import { getMimeValues } from "@/components/data-table/mime-cell";
import { cn } from "@/utils/cn";
import { Logger } from "@/utils/Logger";
import { prettyNumber } from "@/utils/numbers";
import { renderHTML } from "../core/RenderHTML";
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
  target_direction?: "increase" | "decrease";
  slot?: object;
}

export class StatPlugin implements IStatelessPlugin<Data> {
  tagName = "marimo-stat";

  validator = z.object({
    value: z.union([z.string(), z.number(), z.boolean()]).optional(),
    label: z.string().optional(),
    caption: z.string().optional(),
    bordered: z.boolean().default(false),
    direction: z.enum(["increase", "decrease"]).optional(),
    target_direction: z.enum(["increase", "decrease"]).default("increase"),
    slot: z.any().optional(),
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
  target_direction,
  slot,
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

  const onTarget = direction === target_direction;
  const fillColor = onTarget ? "var(--grass-8)" : "var(--red-8)";
  const strokeColor = onTarget ? "var(--grass-9)" : "var(--red-9)";

  const renderSlot = () => {
    const mimeValues = getMimeValues(slot);
    if (mimeValues?.[0]) {
      const { mimetype, data } = mimeValues[0];
      if (mimetype !== "text/html") {
        Logger.warn(`Expected text/html, got ${mimetype}`);
      }
      return renderHTML({ html: data, alwaysSanitizeHtml: true });
    }
  };

  return (
    <div
      className={cn(
        "text-card-foreground p-6",
        bordered && "rounded-xl border shadow bg-card",
      )}
    >
      {label && (
        <div className="flex flex-row items-center justify-between space-y-0 pb-2">
          <h3 className="tracking-tight text-sm font-medium">{label}</h3>
        </div>
      )}
      <div className="pt-0 flex flex-row gap-3.5">
        <div>
          <div className="text-2xl font-bold">{renderPrettyValue()}</div>
          {caption && (
            <p className="pt-1 text-xs text-muted-foreground flex align-center whitespace-nowrap">
              {direction === "increase" && (
                <TriangleIcon
                  className="w-4 h-4 mr-1 p-0.5"
                  fill={fillColor}
                  stroke={strokeColor}
                />
              )}
              {direction === "decrease" && (
                <TriangleIcon
                  className="w-4 h-4 mr-1 p-0.5 transform rotate-180"
                  fill={fillColor}
                  stroke={strokeColor}
                />
              )}
              {caption}
            </p>
          )}
        </div>
        {slot && <div className="[--slot:true]">{renderSlot()}</div>}
      </div>
    </div>
  );
};
