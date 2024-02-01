/* Copyright 2024 Marimo. All rights reserved. */
import React, { PropsWithChildren } from "react";

import { z } from "zod";
import { IStatelessPlugin, IStatelessPluginProps } from "../stateless-plugin";
import { renderHTML } from "../core/RenderHTML";
import { Progress } from "@/components/ui/progress";
import { Loader2Icon } from "lucide-react";
import { clamp } from "@/utils/math";
import humanizeDuration from "humanize-duration";

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
  /**
   * The estimated time remaining in seconds.
   */
  eta?: number;
  /**
   * The rate of progress in items per second.
   */
  rate?: number;
}

export class ProgressPlugin implements IStatelessPlugin<Data> {
  tagName = "marimo-progress";

  validator = z.object({
    title: z.string().optional(),
    subtitle: z.string().optional(),
    progress: z.union([z.number(), z.boolean()]),
    total: z.number().optional(),
    eta: z.number().optional(),
    rate: z.number().optional(),
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
  eta,
  rate,
}: PropsWithChildren<Data>): JSX.Element => {
  const alignment =
    typeof progress === "number" ? "items-start" : "items-center";

  const renderProgress = () => {
    // With a known total, show a progress bar.
    if (typeof progress === "number" && total != null && total > 0) {
      return (
        <div className="flex gap-3 text-sm text-muted-foreground items-baseline">
          <Progress value={clampProgress((progress / total) * 100)} />
          <span className="flex-shrink-0">
            {progress} / {total}
          </span>
        </div>
      );
    }

    // With an unknown total, show a spinner.
    return (
      <Loader2Icon className="w-12 h-12 animate-spin text-primary mx-auto" />
    );
  };

  const renderMeta = () => {
    const hasCompleted =
      typeof progress === "number" && total != null && progress >= total;

    const elements: React.ReactNode[] = [];
    if (rate) {
      elements.push(
        <span key="rate">{rate} iter/s</span>,
        <span key="spacer-rate">&middot;</span>,
      );
    }

    if (!hasCompleted && eta) {
      elements.push(
        <span key="eta">ETA {prettyTime(eta)}</span>,
        <span key="spacer-eta">&middot;</span>,
      );
    }

    if (hasCompleted && rate) {
      const totalTime = progress / rate;
      elements.push(
        <span key="completed">Total time {prettyTime(totalTime)}</span>,
        <span key="spacer-completed">&middot;</span>,
      );
    }

    // pop the last spacer
    elements.pop();

    if (elements.length > 0) {
      return (
        <div className="flex gap-2 text-muted-foreground text-sm">
          {elements}
        </div>
      );
    }
  };

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
      <div className="mt-2 w-full flex flex-col gap-1">
        {renderProgress()}
        {renderMeta()}
      </div>
    </div>
  );
};

function clampProgress(progress: number): number {
  return clamp(progress, 0, 100);
}

const shortDuration = humanizeDuration.humanizer({
  language: "shortEn",
  languages: {
    shortEn: {
      y: () => "y",
      mo: () => "mo",
      w: () => "w",
      d: () => "d",
      h: () => "h",
      m: () => "m",
      s: () => "s",
      ms: () => "ms",
    },
  },
});
export function prettyTime(seconds: number): string {
  return shortDuration(seconds * 1000, {
    language: "shortEn",
    largest: 2,
    spacer: "",
    maxDecimalPoints: 2,
  });
}
