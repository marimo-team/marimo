/* Copyright 2026 Marimo. All rights reserved. */

import { PlusIcon, SparklesIcon } from "lucide-react";
import { Tooltip, TooltipProvider } from "@/components/ui/tooltip";
import type { DetectedDataSource } from "@/core/datasets/data-source-discovery";
import { useDataSourceDiscovery } from "@/hooks/useDataSourceDiscovery";
import { useInsertCode } from "./components";
import { cn } from "@/utils/cn";

export const QuickAddDataSources: React.FC<{
  className?: string;
  sources: DetectedDataSource[];
  onAdd: (source: DetectedDataSource) => void;
}> = ({ className, sources, onAdd }) => {
  if (sources.length === 0) {
    return null;
  }

  return (
    <section
      aria-labelledby="quick-add-data-sources-title"
      className={cn(
        "rounded-full bg-[linear-gradient(135deg,var(--blue-2),var(--purple-3))] px-3 py-2",
        className,
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <div className="mr-1 flex items-center gap-1.5">
          <SparklesIcon className="h-3.5 w-3.5 text-(--blue-9)" />
          <h3 id="quick-add-data-sources-title" className="text-sm font-medium">
            Quick add
          </h3>
        </div>
        <TooltipProvider delayDuration={200}>
          {sources.map((source) => (
            <Tooltip
              key={source.id}
              side="bottom"
              content={<DetectedDataSourceDetails source={source} />}
            >
              <button
                type="button"
                aria-label={`Add ${source.displayName} connection`}
                className="inline-flex items-center gap-1 rounded-full border border-border/60 bg-background/70 px-2.5 py-1 text-xs font-medium text-foreground/90 backdrop-blur-xs transition-colors hover:border-(--blue-7) hover:bg-background focus:outline-hidden focus:ring-2 focus:ring-ring focus:ring-offset-2"
                onClick={() => onAdd(source)}
              >
                <PlusIcon className="h-3 w-3 text-muted-foreground" />
                {source.displayName}
              </button>
            </Tooltip>
          ))}
        </TooltipProvider>
      </div>
    </section>
  );
};

const DetectedDataSourceDetails: React.FC<{
  source: DetectedDataSource;
}> = ({ source }) => (
  <div className="min-w-64 space-y-2 py-1">
    <div>
      <div className="font-medium">{source.displayName}</div>
      <div className="text-xs text-muted-foreground">
        Detected from{" "}
        {source.origins.map((origin) => origin.label).join(" and ")}
      </div>
    </div>
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
      {source.configuration.map((item) => (
        <div
          className="contents"
          key={
            item.value.kind === "environment-variable"
              ? item.value.name
              : `${item.field}:${item.value.value}`
          }
        >
          <dt className="text-muted-foreground">{item.field}</dt>
          <dd>
            <code>
              {item.value.kind === "environment-variable"
                ? `os.environ["${item.value.name}"]`
                : item.value.value}
            </code>
          </dd>
        </div>
      ))}
    </dl>
    <div className="text-xs text-muted-foreground">
      Click to add a configured cell.
    </div>
  </div>
);

export const AutoDiscoveredDataSources: React.FC<{
  onSubmit: () => void;
  className?: string;
}> = ({ onSubmit, className }) => {
  const insertCode = useInsertCode();
  const { data } = useDataSourceDiscovery();

  return (
    <QuickAddDataSources
      className={className}
      sources={data ?? []}
      onAdd={(source) => {
        insertCode(source.code);
        onSubmit();
      }}
    />
  );
};
