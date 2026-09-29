/* Copyright 2026 Marimo. All rights reserved. */

import type { components } from "@marimo-team/marimo-api";
import { ExternalLinkIcon } from "lucide-react";

export type TemplateSummary = components["schemas"]["TemplateSummary"];

interface Props {
  template: TemplateSummary;
  isLaunching: boolean;
  onLaunch: (template: TemplateSummary) => Promise<boolean>;
  onLaunched?: () => void;
}

export const TemplateCard = ({
  template,
  isLaunching,
  onLaunch,
  onLaunched,
}: Props) => {
  const handleLaunch = async () => {
    if (await onLaunch(template)) {
      onLaunched?.();
    }
  };

  return (
    <button
      type="button"
      aria-label={`Use template: ${template.title}`}
      data-testid={`template-card-${template.id}`}
      disabled={isLaunching}
      onClick={handleLaunch}
      className="group overflow-hidden rounded-lg border bg-background text-left shadow-xs transition-colors hover:bg-accent/20 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-wait disabled:opacity-70"
    >
      <img
        src={template.previewUrl}
        alt=""
        className="h-28 w-full border-b bg-(--slate-2) object-cover"
      />
      <div className="relative flex min-h-24 flex-col gap-1 p-4 pr-10">
        <h3 className="font-medium text-foreground">{template.title}</h3>
        <p className="text-sm text-muted-foreground">
          {isLaunching ? "Opening template…" : template.description}
        </p>
        <ExternalLinkIcon className="absolute right-4 top-4 h-5 w-5 text-primary opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" />
      </div>
    </button>
  );
};
