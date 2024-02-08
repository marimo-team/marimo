/* Copyright 2024 Marimo. All rights reserved. */

import { z } from "zod";
import { IStatelessPlugin, IStatelessPluginProps } from "../stateless-plugin";
import { TriangleIcon } from "lucide-react";
import { cn } from "@/utils/cn";

interface Data {
  value: string;
  label?: string;
  caption?: string;
  bordered?: boolean;
  direction?: "increase" | "decrease";
}

export class StatPlugin implements IStatelessPlugin<Data> {
  tagName = "marimo-stat";

  validator = z.object({
    value: z.string(),
    label: z.string().optional(),
    caption: z.string().optional(),
    bordered: z.boolean().default(false),
    direction: z.enum(["increase", "decrease"]).optional(),
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
}) => {
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
        <div className="text-2xl font-bold">{value}</div>
        {caption && (
          <p className="pt-1 text-xs text-muted-foreground flex align-center">
            {direction === "increase" && (
              <TriangleIcon
                className="w-4 h-4 mr-1 p-0.5"
                fill="var(--grass-8)"
                stroke="var(--grass-9)"
              />
            )}
            {direction === "decrease" && (
              <TriangleIcon
                className="w-4 h-4 mr-1 p-0.5 transform rotate-180"
                fill="var(--red-8)"
                stroke="var(--red-9)"
              />
            )}
            {caption}
          </p>
        )}
      </div>
    </div>
  );
};
