/* Copyright 2023 Marimo. All rights reserved. */
import { PropsWithChildren } from "react";

import { z } from "zod";
import { IStatelessPlugin, IStatelessPluginProps } from "../stateless-plugin";
import { renderHTML } from "../core/RenderHTML";
import { Progress } from "@/components/ui/progress";
import { Loader2Icon } from "lucide-react";

interface Data {
  /**
   * The title of the progress bar.
   */
  title?: string;
  /**
   * The subtitle of the progress bar.
   */
  subtitle?: string;
  /**
   * The progress of the progress bar.
   * Number from 0 to 100, or `true` to indicate indeterminate progress if the count is unknown.
   */
  progress: number | boolean;
  /**
   * The total value of the progress bar.
   */
  total?: number;
}

export class ProgressPlugin implements IStatelessPlugin<Data> {
  tagName = "marimo-progress";

  validator = z.object({
    title: z.string().optional(),
    subtitle: z.string().optional(),
    progress: z.union([z.number(), z.boolean()]),
    total: z.number().optional(),
  });

  render(props: IStatelessPluginProps<Data>): JSX.Element {
    return <ProgressComponent {...props.data} />;
  }
}

export const ProgressComponent = ({
  title,
  subtitle,
  progress,
  total,
}: PropsWithChildren<Data>): JSX.Element => {
  const alignment =
    typeof progress === "number" ? "items-start" : "items-center";
  return (
    <div className={`flex flex-col ${alignment} max-w-sm p-6 mx-auto`}>
      {title && (
        <div className="text-lg font-bold text-foreground/60">
          {renderHTML({ html: title })}
        </div>
      )}
      {subtitle && (
        <div className="text-sm text-muted-foreground">
          {renderHTML({ html: subtitle })}
        </div>
      )}
      <div className="mt-2 w-full">
        {typeof progress === "number" && total != null && total > 0 ? (
          <div className="flex gap-3 text-sm text-muted-foreground items-baseline">
            <Progress value={clampProgress((progress / total) * 100)} />
            <span className="flex-shrink-0">
              {progress} / {total}
            </span>
          </div>
        ) : (
          <Loader2Icon className="w-12 h-12 animate-spin text-primary mx-auto" />
        )}
      </div>
    </div>
  );
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}
function clampProgress(progress: number): number {
  return clamp(progress, 0, 100);
}
